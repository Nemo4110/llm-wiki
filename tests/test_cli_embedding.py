"""
CLI 端到端测试：验证 wiki index 和 wiki query --semantic

运行方式：
    pytest tests/test_cli_embedding.py
    python tests/test_cli_embedding.py
"""

import shutil
import sys
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm_wiki.commands import cli


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
    def test_index_outputs_provider_name(self, temp_wiki_dir):
        """index 命令应正确解析配置并输出 provider 名称，随后因无真实 Ollama 服务而失败"""
        runner = CliRunner()
        result = runner.invoke(cli, ["--wiki-dir", str(temp_wiki_dir), "index"])
        assert result.exit_code == 1
        assert "使用提供者: ollama:mock-model" in result.output


class TestCliQuery:
    def test_semantic_query_requires_index(self, temp_wiki_dir):
        """--semantic 查询在没有缓存时应提示先运行 index"""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--wiki-dir", str(temp_wiki_dir), "query", "attention", "--semantic"]
        )
        assert result.exit_code == 1
        assert "embedding 索引为空" in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
