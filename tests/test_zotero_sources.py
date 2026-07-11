import argparse
import importlib.util
from pathlib import Path

import pytest


def _load_module():
    project_root = Path(__file__).resolve().parent.parent
    script_path = project_root / "scripts" / "zotero_sources.py"
    spec = importlib.util.spec_from_file_location("zotero_sources", str(script_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_iter_attachments_reads_private_metadata(tmp_path):
    mod = _load_module()
    metadata = tmp_path / "sources" / "zotero" / "metadata.yaml"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(
        """
version: 1
collections:
  - name: 技术沉思录
    zotero_collection_key: LTECJSFB
    items:
      - title: 深入FlashAttention
        zotero_item_key: 9HQB5NEF
        attachments:
          - zotero_attachment_key: RTMTYN5Q
            content_type: application/pdf
            filename: 深入FlashAttention.pdf
            local_path: C:/Zotero/storage/RTMTYN5Q/深入FlashAttention.pdf
            source_alias: sources/zotero/技术沉思录/9HQB5NEF/RTMTYN5Q.pdf
""",
        encoding="utf-8",
    )

    attachments = list(mod.iter_attachments(metadata))

    assert len(attachments) == 1
    assert attachments[0].collection_name == "技术沉思录"
    assert attachments[0].item_key == "9HQB5NEF"
    assert attachments[0].attachment_key == "RTMTYN5Q"
    assert attachments[0].source_alias == Path("sources/zotero/技术沉思录/9HQB5NEF/RTMTYN5Q.pdf")


def test_materialize_creates_symlink_inside_sources_zotero(tmp_path):
    mod = _load_module()
    source_file = tmp_path / "zotero-storage" / "paper.pdf"
    source_file.parent.mkdir()
    source_file.write_text("raw pdf placeholder", encoding="utf-8")

    metadata = tmp_path / "sources" / "zotero" / "metadata.yaml"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(
        f"""
version: 1
collections:
  - name: 技术沉思录
    zotero_collection_key: LTECJSFB
    items:
      - title: 深入FlashAttention
        zotero_item_key: 9HQB5NEF
        attachments:
          - zotero_attachment_key: RTMTYN5Q
            local_path: {source_file.as_posix()}
            source_alias: sources/zotero/技术沉思录/9HQB5NEF/RTMTYN5Q.pdf
""",
        encoding="utf-8",
    )

    result = mod.materialize(metadata, tmp_path)
    link = tmp_path / "sources" / "zotero" / "技术沉思录" / "9HQB5NEF" / "RTMTYN5Q.pdf"

    assert result.created == 1
    assert link.is_symlink()
    assert link.resolve() == source_file.resolve()


def test_materialize_skips_existing_matching_symlink(tmp_path):
    mod = _load_module()
    source_file = tmp_path / "zotero-storage" / "paper.pdf"
    source_file.parent.mkdir()
    source_file.write_text("raw pdf placeholder", encoding="utf-8")

    metadata = tmp_path / "sources" / "zotero" / "metadata.yaml"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(
        f"""
version: 1
collections:
  - name: 技术沉思录
    zotero_collection_key: LTECJSFB
    items:
      - title: 深入FlashAttention
        zotero_item_key: 9HQB5NEF
        attachments:
          - zotero_attachment_key: RTMTYN5Q
            local_path: {source_file.as_posix()}
            source_alias: sources/zotero/技术沉思录/9HQB5NEF/RTMTYN5Q.pdf
""",
        encoding="utf-8",
    )

    first = mod.materialize(metadata, tmp_path)
    second = mod.materialize(metadata, tmp_path)

    assert first.created == 1
    assert second.created == 0
    assert second.skipped == 1
    assert second.errors == []


def test_materialize_rejects_alias_outside_sources_zotero(tmp_path):
    mod = _load_module()
    source_file = tmp_path / "zotero-storage" / "paper.pdf"
    source_file.parent.mkdir()
    source_file.write_text("raw pdf placeholder", encoding="utf-8")

    metadata = tmp_path / "sources" / "zotero" / "metadata.yaml"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(
        f"""
version: 1
collections:
  - name: 技术沉思录
    items:
      - title: unsafe
        zotero_item_key: 9HQB5NEF
        attachments:
          - zotero_attachment_key: RTMTYN5Q
            local_path: {source_file.as_posix()}
            source_alias: wiki/Unsafe.pdf
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="sources/zotero"):
        mod.materialize(metadata, tmp_path)


def test_main_dry_run_reports_without_creating_link(tmp_path, capsys):
    mod = _load_module()
    source_file = tmp_path / "zotero-storage" / "paper.pdf"
    source_file.parent.mkdir()
    source_file.write_text("raw pdf placeholder", encoding="utf-8")

    metadata = tmp_path / "sources" / "zotero" / "metadata.yaml"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(
        f"""
version: 1
collections:
  - name: 技术沉思录
    items:
      - title: 深入FlashAttention
        zotero_item_key: 9HQB5NEF
        attachments:
          - zotero_attachment_key: RTMTYN5Q
            local_path: {source_file.as_posix()}
            source_alias: sources/zotero/技术沉思录/9HQB5NEF/RTMTYN5Q.pdf
""",
        encoding="utf-8",
    )

    args = argparse.Namespace(metadata=str(metadata), project_root=str(tmp_path), dry_run=True, force=False)
    rc = mod.cmd_materialize(args)
    out = capsys.readouterr().out

    assert rc == 0
    assert "DRY-RUN" in out
    assert not (tmp_path / "sources" / "zotero" / "技术沉思录" / "9HQB5NEF" / "RTMTYN5Q.pdf").exists()
