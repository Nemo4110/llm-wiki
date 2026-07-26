"""Tests for the release package builder."""

from zipfile import ZipFile

from scripts import create_release


def test_build_release_includes_example_config(tmp_path, monkeypatch):
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
    with ZipFile(zip_path) as archive:
        assert "llm-wiki-v9.9.9/config.yaml.example" in archive.namelist()
