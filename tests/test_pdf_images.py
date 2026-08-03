"""Tests for PDF image and figure extraction."""

from pathlib import Path
import subprocess
import sys

import fitz
import pytest

from llm_wiki.pdf_images import (
    extract_embedded_images,
    extract_pdf_images,
    extract_vector_figures,
    parse_pages,
)


_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _make_red_pixmap(size: int = 10) -> fitz.Pixmap:
    """Create a small red RGB pixmap."""
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, size, size))
    for x in range(size):
        for y in range(size):
            pix.set_pixel(x, y, (255, 0, 0))
    return pix


def _make_test_pdf(tmp_path: Path, with_image: bool = False, with_drawing: bool = False) -> Path:
    """Create a minimal PDF for testing extraction paths."""
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)

    if with_image:
        pix = _make_red_pixmap()
        try:
            page.insert_image(fitz.Rect(10, 10, 100, 100), pixmap=pix)
        finally:
            pix = None

    if with_drawing:
        shape = page.new_shape()
        shape.draw_rect(fitz.Rect(150, 50, 250, 150))
        shape.finish(color=(0, 1, 0), fill=(0, 1, 0))
        shape.commit()

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_parse_pages_all_and_single_and_range(tmp_path: Path) -> None:
    pdf_path = _make_test_pdf(tmp_path)
    doc = fitz.open(str(pdf_path))
    try:
        assert list(parse_pages(doc, None)) == [0]
        assert list(parse_pages(doc, "1")) == [0]
        assert list(parse_pages(doc, "1-5")) == [0]
        assert list(parse_pages(doc, "2")) == []
        assert list(parse_pages(doc, "5-10")) == []
    finally:
        doc.close()


def test_parse_pages_invalid_input(tmp_path: Path) -> None:
    pdf_path = _make_test_pdf(tmp_path)
    doc = fitz.open(str(pdf_path))
    try:
        with pytest.raises(ValueError, match="Invalid page range"):
            list(parse_pages(doc, "a"))
        with pytest.raises(ValueError, match="Invalid page range"):
            list(parse_pages(doc, "1-b"))
    finally:
        doc.close()


def test_extract_embedded_images_finds_raster_image(tmp_path: Path) -> None:
    pdf_path = _make_test_pdf(tmp_path, with_image=True)
    output_dir = tmp_path / "images"

    with fitz.open(str(pdf_path)) as doc:
        results = extract_embedded_images(doc, output_dir)

    assert len(results) == 1
    img = results[0]
    assert img["page"] == 1
    assert img["index"] == 0
    assert img["ext"] == "png"
    assert Path(img["path"]).exists()


def test_extract_vector_figures_finds_drawing_cluster(tmp_path: Path) -> None:
    pdf_path = _make_test_pdf(tmp_path, with_drawing=True)
    output_dir = tmp_path / "figures"

    with fitz.open(str(pdf_path)) as doc:
        results = extract_vector_figures(doc, output_dir, dpi=100)

    assert len(results) >= 1
    fig = results[0]
    assert fig["page"] == 1
    assert fig["index"] == 0
    assert Path(fig["path"]).exists()
    assert Path(fig["path"]).suffix == ".png"
    assert len(fig["bbox"]) == 4


def test_extract_pdf_images_combines_both_paths(tmp_path: Path) -> None:
    pdf_path = _make_test_pdf(tmp_path, with_image=True, with_drawing=True)
    output_dir = tmp_path / "out"

    result = extract_pdf_images(pdf_path, output_dir, dpi=100)

    assert len(result["images"]) == 1
    assert len(result["figures"]) >= 1
    assert (output_dir / "images").exists()
    assert (output_dir / "figures").exists()


def test_extract_pdf_images_respects_page_range(tmp_path: Path) -> None:
    first_page_pdf = _make_test_pdf(tmp_path, with_image=True)
    # Add a second page without an image.
    pdf_path = tmp_path / "two_pages.pdf"
    with fitz.open(str(first_page_pdf)) as doc:
        doc.new_page(width=300, height=300)
        doc.save(str(pdf_path))

    output_dir = tmp_path / "out"
    result = extract_pdf_images(pdf_path, output_dir, pages="2")
    assert len(result["images"]) == 0


def test_extract_pdf_images_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        extract_pdf_images(tmp_path / "missing.pdf", tmp_path / "out")


def test_extract_pdf_images_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        extract_pdf_images(tmp_path, tmp_path / "out")


def test_extract_embedded_images_skips_duplicate_xrefs(tmp_path: Path) -> None:
    """Images reused on multiple pages should only be extracted once."""
    pdf_path = tmp_path / "reused.pdf"
    doc = fitz.open()
    pix = _make_red_pixmap()
    try:
        page1 = doc.new_page(width=300, height=300)
        page1.insert_image(fitz.Rect(10, 10, 100, 100), pixmap=pix)

        page2 = doc.new_page(width=300, height=300)
        page2.insert_image(fitz.Rect(10, 10, 100, 100), pixmap=pix)

        doc.save(str(pdf_path))
    finally:
        pix = None
        doc.close()

    output_dir = tmp_path / "images"
    with fitz.open(str(pdf_path)) as doc:
        results = extract_embedded_images(doc, output_dir)

    # Two page references but one underlying image xref.
    assert len(results) == 1


def test_read_pdf_script_extract_images_cli(tmp_path: Path) -> None:
    """The CLI ``--extract-images`` path writes images and exits cleanly."""
    pdf_path = _make_test_pdf(tmp_path, with_image=True, with_drawing=True)
    image_dir = tmp_path / "extracted"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/read_pdf.py",
            str(pdf_path),
            "--extract-images",
            "--image-dir",
            str(image_dir),
            "--image-dpi",
            "100",
        ],
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "内嵌位图" in result.stdout
    assert "矢量图表" in result.stdout
    assert (image_dir / "images").exists()
    assert (image_dir / "figures").exists()
