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
    assert attachments[0].source_alias == Path(
        "sources/zotero/技术沉思录/9HQB5NEF/RTMTYN5Q.pdf"
    )


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

    args = argparse.Namespace(
        metadata=str(metadata), project_root=str(tmp_path), dry_run=True, force=False
    )
    rc = mod.cmd_materialize(args)
    out = capsys.readouterr().out

    assert rc == 0
    assert "DRY-RUN" in out
    assert not (
        tmp_path / "sources" / "zotero" / "技术沉思录" / "9HQB5NEF" / "RTMTYN5Q.pdf"
    ).exists()


def _write_two_item_metadata(tmp_path, src_a, src_b):
    metadata = tmp_path / "sources" / "zotero" / "metadata.yaml"
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(
        f"""
version: 1
collections:
  - name: coll
    zotero_collection_key: COLLKEY1
    items:
      - title: A
        zotero_item_key: ITEMA001
        attachments:
          - zotero_attachment_key: failme
            local_path: {src_a.as_posix()}
            source_alias: sources/zotero/coll/ITEMA001/a.pdf
      - title: B
        zotero_item_key: ITEMB002
        attachments:
          - zotero_attachment_key: okone
            local_path: {src_b.as_posix()}
            source_alias: sources/zotero/coll/ITEMB002/b.pdf
""",
        encoding="utf-8",
    )
    return metadata


def _patch_symlink_failure(monkeypatch, only=None):
    from pathlib import Path as _P

    original = _P.symlink_to

    def fake(self, target, *args, **kwargs):
        if only is None or only in str(target):
            raise OSError("privilege not held")
        return original(self, target, *args, **kwargs)

    monkeypatch.setattr(_P, "symlink_to", fake)


def test_symlink_oserror_defaults_to_metadata_fallback(tmp_path, monkeypatch):
    mod = _load_module()
    src = tmp_path / "storage" / "a.pdf"
    src.parent.mkdir()
    src.write_text("pdf bytes", encoding="utf-8")
    src_b = tmp_path / "storage" / "b.pdf"
    src_b.write_text("b bytes", encoding="utf-8")
    metadata = _write_two_item_metadata(tmp_path, src, src_b)
    _patch_symlink_failure(monkeypatch, only="a.pdf")

    result = mod.materialize(metadata, tmp_path)

    alias_a = tmp_path / "sources" / "zotero" / "coll" / "ITEMA001" / "a.pdf"
    assert result.created == 1  # b 仍成功
    assert not alias_a.exists() and not alias_a.is_symlink()
    assert result.errors == []
    assert len(result.degraded) == 1
    assert "metadata" in result.degraded[0]


def test_symlink_fallback_copy_creates_regular_file(tmp_path, monkeypatch):
    mod = _load_module()
    src = tmp_path / "storage" / "a.pdf"
    src.parent.mkdir()
    src.write_text("pdf bytes", encoding="utf-8")
    src_b = tmp_path / "storage" / "b.pdf"
    src_b.write_text("b bytes", encoding="utf-8")
    metadata = _write_two_item_metadata(tmp_path, src, src_b)
    _patch_symlink_failure(monkeypatch, only="a.pdf")

    result = mod.materialize(metadata, tmp_path, on_symlink_error="copy")

    alias_a = tmp_path / "sources" / "zotero" / "coll" / "ITEMA001" / "a.pdf"
    assert alias_a.is_file() and not alias_a.is_symlink()
    assert alias_a.read_bytes() == src.read_bytes()
    assert any("copy" in entry for entry in result.degraded)
    assert result.errors == []


def test_symlink_fallback_hardlink_shares_inode(tmp_path, monkeypatch):
    mod = _load_module()
    src = tmp_path / "storage" / "a.pdf"
    src.parent.mkdir()
    src.write_text("pdf bytes", encoding="utf-8")
    src_b = tmp_path / "storage" / "b.pdf"
    src_b.write_text("b bytes", encoding="utf-8")
    metadata = _write_two_item_metadata(tmp_path, src, src_b)
    _patch_symlink_failure(monkeypatch, only="a.pdf")

    result = mod.materialize(metadata, tmp_path, on_symlink_error="hardlink")

    alias_a = tmp_path / "sources" / "zotero" / "coll" / "ITEMA001" / "a.pdf"
    import os

    assert os.path.samefile(alias_a, src)
    assert any("hardlink" in entry for entry in result.degraded)


def test_copy_fallback_rerun_skips_matching_copy(tmp_path, monkeypatch):
    mod = _load_module()
    src = tmp_path / "storage" / "a.pdf"
    src.parent.mkdir()
    src.write_text("pdf bytes", encoding="utf-8")
    src_b = tmp_path / "storage" / "b.pdf"
    src_b.write_text("b bytes", encoding="utf-8")
    metadata = _write_two_item_metadata(tmp_path, src, src_b)
    _patch_symlink_failure(monkeypatch, only="a.pdf")

    first = mod.materialize(metadata, tmp_path, on_symlink_error="copy")
    second = mod.materialize(metadata, tmp_path, on_symlink_error="copy")

    assert len(first.degraded) == 1
    assert second.errors == []
    assert second.skipped == 2


def test_unknown_fallback_mode_rejected(tmp_path):
    mod = _load_module()
    src = tmp_path / "storage" / "a.pdf"
    src.parent.mkdir()
    src.write_text("pdf bytes", encoding="utf-8")
    src_b = tmp_path / "storage" / "b.pdf"
    src_b.write_text("b bytes", encoding="utf-8")
    metadata = _write_two_item_metadata(tmp_path, src, src_b)

    with pytest.raises(ValueError, match="on_symlink_error"):
        mod.materialize(metadata, tmp_path, on_symlink_error="bogus")
