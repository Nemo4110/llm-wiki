"""
Mock 测试：验证 embedding + 混合检索链路

不需要外部服务，使用固定维度的确定性向量模拟 embedding provider。
运行方式：
    pytest tests/test_embedding_mock.py
    python tests/test_embedding_mock.py
"""

import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm_wiki.core import WikiManager
from llm_wiki.embeddings import EmbeddingProvider
from llm_wiki.retrieval import EmbeddingIndex


class MockEmbeddingProvider(EmbeddingProvider):
    """返回固定维度、基于文本哈希的确定性向量，便于复现测试结果"""

    def __init__(self, dimension: int = 8):
        self._dimension = dimension

    def embed(self, texts):
        embeddings = []
        for text in texts:
            h = hash(text) % 10000
            vec_rng = np.random.default_rng(seed=42 + h)
            vec = vec_rng.random(self._dimension).astype(np.float32)
            vec = vec / np.linalg.norm(vec)
            embeddings.append(vec.tolist())
        return embeddings

    @property
    def dimension(self):
        return self._dimension

    @property
    def name(self):
        return f"mock:{self._dimension}"


@pytest.fixture
def temp_wiki():
    """提供一个包含测试页面的临时 wiki 目录"""
    tmp_dir = Path(tempfile.mkdtemp(prefix="llm-wiki-test-"))
    wiki_dir = tmp_dir / "wiki"
    wiki_dir.mkdir()
    (tmp_dir / "CLAUDE.md").write_text("# test", encoding="utf-8")

    wiki = WikiManager(wiki_dir)
    provider = MockEmbeddingProvider(dimension=8)

    pages_data = [
        (
            "Transformer",
            "Transformer 使用自注意力机制，彻底改变了 NLP 领域。",
            ["AI/ML", "NLP"],
        ),
        (
            "LoRA",
            "LoRA 是一种参数高效的微调方法，只需训练少量低秩矩阵。",
            ["AI/ML", "微调"],
        ),
        (
            "Docker",
            "Docker 是一种容器化技术，用于部署和隔离应用。",
            ["DevOps", "容器"],
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

    yield wiki, provider

    shutil.rmtree(tmp_dir)


class TestEmbeddingIndexBuild:
    def test_initial_build_indexes_all_pages(self, temp_wiki):
        wiki, provider = temp_wiki
        index = EmbeddingIndex(wiki, provider)
        indexed, skipped = index.build()
        assert indexed == 3
        assert skipped == 0

    def test_rebuild_skips_unchanged_pages(self, temp_wiki):
        wiki, provider = temp_wiki
        index = EmbeddingIndex(wiki, provider)
        index.build()
        indexed, skipped = index.build()
        assert indexed == 0
        assert skipped == 3

    def test_incremental_update_only_changed_page(self, temp_wiki):
        wiki, provider = temp_wiki
        index = EmbeddingIndex(wiki, provider)
        index.build()

        page = wiki.get_page("LoRA")
        new_content = page.content + "\n\n它常与 Transformer 结合使用。"
        wiki.update_page("LoRA", new_content, merge_strategy="replace")

        indexed, skipped = index.build()
        assert indexed == 1
        assert skipped == 2


class TestEmbeddingIndexSearch:
    def test_search_returns_ranked_results(self, temp_wiki):
        wiki, provider = temp_wiki
        index = EmbeddingIndex(wiki, provider)
        index.build()

        results = index.search("微调方法", top_k=5)
        assert len(results) > 0
        titles = [r[0] for r in results]
        assert "LoRA" in titles

    def test_search_respects_top_k(self, temp_wiki):
        wiki, provider = temp_wiki
        index = EmbeddingIndex(wiki, provider)
        index.build()

        results = index.search("容器部署", top_k=2)
        assert len(results) <= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
