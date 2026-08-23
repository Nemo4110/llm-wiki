from __future__ import annotations

from pathlib import Path

from src.llm_wiki.init_cmd import scaffold


PRIVATE_RULES = {
    "/var/",
    "/temp/",
    "/sources/zotero/",
    ".mcp.json",
    "config.yaml",
    "log.md",
}


def test_scaffold_creates_private_state_gitignore(tmp_path: Path):
    actions = scaffold(tmp_path)

    gitignore = tmp_path / ".gitignore"
    assert gitignore.exists()
    lines = set(gitignore.read_text(encoding="utf-8").splitlines())
    assert PRIVATE_RULES.issubset(lines)
    assert "created  .gitignore" in actions


def test_scaffold_extends_existing_gitignore_without_overwriting(tmp_path: Path):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.log\nvar/\n", encoding="utf-8")

    actions = scaffold(tmp_path)
    text = gitignore.read_text(encoding="utf-8")
    lines = text.splitlines()

    assert lines[:2] == ["*.log", "var/"]
    assert lines.count("var/") == 1
    assert "/var/" not in lines
    normalized = {line.lstrip("/") for line in lines}
    assert {rule.lstrip("/") for rule in PRIVATE_RULES}.issubset(normalized)
    assert "updated  .gitignore" in actions


def test_scaffold_gitignore_is_idempotent_even_with_force(tmp_path: Path):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("custom-rule\n", encoding="utf-8")

    scaffold(tmp_path)
    first = gitignore.read_text(encoding="utf-8")
    actions = scaffold(tmp_path, force=True)
    second = gitignore.read_text(encoding="utf-8")

    assert first == second
    assert second.startswith("custom-rule\n")
    assert "kept     .gitignore" in actions
