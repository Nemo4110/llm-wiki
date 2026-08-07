"""Tests for the release package builder."""

from pathlib import Path
from zipfile import ZipFile

from scripts import create_release


def test_claude_protocol_is_relative_symlink():
    root = Path(__file__).resolve().parents[1]
    link = root / "CLAUDE.md"

    assert link.is_symlink()
    assert link.readlink() == Path("AGENTS.md")
    assert link.read_bytes() == (root / "AGENTS.md").read_bytes()


def test_build_release_includes_example_config(tmp_path, monkeypatch):
    protocol = "# Unified protocol\n"
    (tmp_path / "AGENTS.md").write_text(protocol, encoding="utf-8")
    (tmp_path / "CLAUDE.md").symlink_to("AGENTS.md")
    (tmp_path / "config.yaml.example").write_text(
        "embedding:\n  enabled: false\n",
        encoding="utf-8",
    )
    release_dir = tmp_path / "release"
    monkeypatch.setattr(create_release, "ROOT", tmp_path)
    monkeypatch.setattr(create_release, "RELEASE_DIR", release_dir)

    package_dir, zip_path = create_release.build_release("9.9.9")

    assert (package_dir / "config.yaml.example").read_text(encoding="utf-8") == (
        "embedding:\n  enabled: false\n"
    )
    packaged_claude = package_dir / "CLAUDE.md"
    assert packaged_claude.is_file()
    assert not packaged_claude.is_symlink()
    assert packaged_claude.read_text(encoding="utf-8") == protocol
    with ZipFile(zip_path) as archive:
        assert "llm-wiki-v9.9.9/config.yaml.example" in archive.namelist()
        archived_claude = archive.read("llm-wiki-v9.9.9/CLAUDE.md").decode()
        assert archived_claude.replace("\r\n", "\n") == protocol
