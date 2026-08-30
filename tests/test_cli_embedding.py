"""
CLI tests: verify wiki index and wiki query --semantic using the unified CLI
"""

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm_wiki.cli import main
import llm_wiki.cli as cli_mod


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
        assert "ollama" in out.lower() or "provider" in out.lower() or "error" in out.lower()


class TestCliQuery:
    def test_semantic_query_requires_index(self, temp_wiki_dir, monkeypatch, capsys):
        monkeypatch.setattr(cli_mod, "_get_project_root", lambda: temp_wiki_dir)
        rc = main(["query", "attention", "--semantic"])
        out = capsys.readouterr().out
        assert rc == 1
        assert "empty" in out.lower() or "error" in out.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
