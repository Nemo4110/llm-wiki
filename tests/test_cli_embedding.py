"""
CLI tests: verify wiki index and wiki query --semantic using the unified CLI
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import llm_wiki.cli as cli_mod
from llm_wiki.cli import main


@pytest.fixture
def temp_wiki_dir():
    """提供一个包含测试页面和启用了 embedding 配置的临时 wiki 目录"""
    tmp_dir = Path(tempfile.mkdtemp(prefix="llm-wiki-cli-test-"))
    wiki_dir = tmp_dir / "wiki"
    wiki_dir.mkdir()
    (tmp_dir / "CLAUDE.md").write_text("# test", encoding="utf-8")

    pages = [
        ("Transformer", "# Transformer\n\nSelf-attention mechanism."),
        ("LoRA", "# LoRA\n\nLow-rank adaptation for fine-tuning."),
    ]
    for title, content in pages:
        (wiki_dir / f"{title}.md").write_text(
            f"---\ncreated: 2026-04-14\nupdated: 2026-04-14\ntags:\n  - AI\nstatus: active\n---\n\n{content}",
            encoding="utf-8",
        )

    config_content = """
embedding:
  enabled: true
  provider: ollama
  model: mock-model
"""
    (tmp_dir / "config.yaml").write_text(config_content, encoding="utf-8")

    yield tmp_dir

    shutil.rmtree(tmp_dir)


class TestCliIndex:
    def test_index_outputs_provider_or_error(self, temp_wiki_dir, monkeypatch, capsys):
        monkeypatch.setattr(cli_mod, "_get_project_root", lambda: temp_wiki_dir)
        rc = main(["index"])
        out = capsys.readouterr().out
        assert rc == 1
        assert (
            "ollama" in out.lower()
            or "provider" in out.lower()
            or "error" in out.lower()
        )


class TestCliQuery:
    def test_semantic_query_requires_index(self, temp_wiki_dir, monkeypatch, capsys):
        monkeypatch.setattr(cli_mod, "_get_project_root", lambda: temp_wiki_dir)
        rc = main(["query", "attention", "--semantic"])
        out = capsys.readouterr().out
        assert rc == 1
        assert "empty" in out.lower() or "error" in out.lower()


class TestInstalledLayout:
    def test_module_help_works_outside_source_checkout(self, tmp_path):
        repo_src = Path(__file__).parent.parent / "src"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(repo_src)

        result = subprocess.run(
            [sys.executable, "-B", "-m", "llm_wiki", "--help"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
        )

        assert result.returncode == 0, result.stderr
        assert "usage: llm-wiki" in result.stdout
        assert "No module named 'src'" not in result.stderr

        init_result = subprocess.run(
            [sys.executable, "-B", "-m", "llm_wiki", "init", str(tmp_path / "kb")],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
        )
        assert init_result.returncode == 0, init_result.stderr
        assert (tmp_path / "kb" / "AGENTS.md").exists()

        check_result = subprocess.run(
            [sys.executable, "-B", "-m", "llm_wiki", "check"],
            cwd=tmp_path / "kb",
            env=env,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
        )
        assert check_result.returncode == 0, check_result.stderr
        assert "Library Import | OK" in check_result.stdout

    def test_legacy_cli_flags_are_accepted(self, temp_wiki_dir, capsys):
        rc = main(
            [
                "--wiki-dir",
                str(temp_wiki_dir),
                "--verbose",
                "query",
                "attention",
                "--save",
            ]
        )
        out = capsys.readouterr().out

        assert rc == 1  # semantic is enabled but the test index is intentionally absent
        assert "unrecognized arguments" not in out.lower()

        lint_rc = main(["--wiki-dir", str(temp_wiki_dir), "lint", "--fix"])
        lint_out = capsys.readouterr().out
        assert lint_rc == 0
        assert "unrecognized arguments" not in lint_out.lower()

        index_rc = main(
            ["--wiki-dir", str(temp_wiki_dir), "index", "--provider", "ollama"]
        )
        index_out = capsys.readouterr().out
        assert index_rc == 1
        assert "unrecognized arguments" not in index_out.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
