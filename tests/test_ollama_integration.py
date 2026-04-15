"""
Ollama 集成测试：在本地 Ollama 可用时验证真实 embedding 链路

运行方式：
    pytest tests/test_ollama_integration.py -v

跳过条件：
    - Ollama 服务未运行在 http://localhost:11434
    - nomic-embed-text 模型未下载
"""

import shutil
import sys
import tempfile
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm_wiki.core import WikiManager
from llm_wiki.embeddings import OllamaEmbeddingProvider
from llm_wiki.retrieval import EmbeddingIndex


OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "nomic-embed-text"


def _ollama_available():
    """检查 Ollama 服务是否可访问"""
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False


ollama_not_available = not _ollama_available()


@pytest.fixture
def temp_wiki_dir():
    """提供一个包含测试页面的临时 wiki 目录"""
    tmp_dir = Path(tempfile.mkdtemp(prefix="llm-wiki-ollama-test-"))
    wiki_dir = tmp_dir / "wiki"
    wiki_dir.mkdir()
    (tmp_dir / "CLAUDE.md").write_text("# test", encoding="utf-8")

    wiki = WikiManager(wiki_dir)
    pages_data = [
        (
            "Transformer",
            "Transformer uses self-attention mechanism and revolutionized NLP.",
            ["AI/ML", "NLP"],
        ),
        (
            "LoRA",
            "LoRA is a parameter-efficient fine-tuning method using low-rank matrices.",
            ["AI/ML", "Fine-tuning"],
        ),
        (
            "Docker",
            "Docker is a containerization technology for deploying applications.",
            ["DevOps", "Container"],
        ),
    ]

    for title, content, tags in pages_data:
        frontmatter = {
            "created": "2026-04-14",
            "updated": "2026-04-14",
            "tags": tags,
            "status": "active",
        }
        wiki.create_page(title, f"# {title}\n\n{content}", frontmatter)

    yield tmp_dir, wiki

    shutil.rmtree(tmp_dir)


@pytest.mark.skipif(ollama_not_available, reason="Ollama not available at localhost:11434")
class TestOllamaEmbeddingIndex:
    def test_ollama_build_index(self, temp_wiki_dir):
        tmp_dir, wiki = temp_wiki_dir
        provider = OllamaEmbeddingProvider(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL)

        index = EmbeddingIndex(wiki, provider)
        indexed, skipped = index.build(force=True)
        assert indexed == 3
        assert skipped == 0

        # 验证缓存文件已生成
        cache_path = tmp_dir / "wiki" / ".cache" / "embeddings.json"
        assert cache_path.exists()

    def test_ollama_semantic_search(self, temp_wiki_dir):
        tmp_dir, wiki = temp_wiki_dir
        provider = OllamaEmbeddingProvider(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL)

        index = EmbeddingIndex(wiki, provider)
        index.build(force=True)

        # 查询与 AI 微调相关的内容
        results = index.search("parameter efficient fine tuning", top_k=3)
        assert len(results) > 0
        titles = [r[0] for r in results]
        assert "LoRA" in titles, f"Expected LoRA in results, got {titles}"

        # 查询与容器相关的内容
        results2 = index.search("container deployment", top_k=3)
        assert len(results2) > 0
        titles2 = [r[0] for r in results2]
        assert "Docker" in titles2, f"Expected Docker in results, got {titles2}"

    def test_ollama_incremental_update(self, temp_wiki_dir):
        tmp_dir, wiki = temp_wiki_dir
        provider = OllamaEmbeddingProvider(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL)

        index = EmbeddingIndex(wiki, provider)
        index.build(force=True)

        # 修改一个页面
        page = wiki.get_page("LoRA")
        new_content = page.content + "\n\nIt is often used with Transformer models."
        wiki.update_page("LoRA", new_content, merge_strategy="replace")

        indexed, skipped = index.build()
        assert indexed == 1
        assert skipped == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
