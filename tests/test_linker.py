"""
Tests for linker.py - Knowledge Linker Engine
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from llm_wiki.linker import (
    KnowledgeLinker,
    PageRelation,
    RelationGraph,
    RelationType,
    _edit_distance,
    _extract_keywords,
    _jaccard_similarity,
    _normalize_title,
)
from llm_wiki.core import WikiManager, WikiPage


class TestUtilityFunctions:
    """测试底层工具函数"""

    def test_extract_keywords_english(self):
        text = "The Transformer architecture is a deep learning model"
        keywords = _extract_keywords(text)
        assert "transformer" in keywords
        assert "architecture" in keywords
        assert "learning" in keywords
        assert "model" in keywords
        assert "the" not in keywords  # 停用词

    def test_extract_keywords_chinese(self):
        text = "Transformer 是一种深度学习模型架构"
        keywords = _extract_keywords(text)
        assert "transformer" in keywords
        # 单字提取 + 连续序列提取
        assert "深" in keywords or "深度" in keywords
        assert "模" in keywords or "模型" in keywords

    def test_jaccard_similarity(self):
        a = {"transformer", "attention", "nlp"}
        b = {"transformer", "attention", "cv"}
        assert _jaccard_similarity(a, b) == 2 / 4  # 交集2，并集4

    def test_jaccard_empty(self):
        assert _jaccard_similarity(set(), set()) == 1.0
        assert _jaccard_similarity(set(), {"a"}) == 0.0

    def test_edit_distance(self):
        assert _edit_distance("kitten", "sitting") == 3
        assert _edit_distance("", "abc") == 3
        assert _edit_distance("abc", "abc") == 0

    def test_normalize_title(self):
        assert _normalize_title("Transformer-Model") == "transformer model"
        assert _normalize_title("LoRA_FineTuning") == "lora finetuning"


class TestKnowledgeLinker:
    """测试 KnowledgeLinker 核心功能"""

    @pytest.fixture
    def temp_wiki(self, tmp_path):
        """创建临时 wiki 目录"""
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        return WikiManager(wiki_dir)

    @pytest.fixture
    def populated_wiki(self, tmp_path):
        """创建包含多个页面的 wiki"""
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        wiki = WikiManager(wiki_dir)

        # 创建测试页面
        pages = [
            ("Transformer", "Transformer 是一种基于注意力机制的序列建模架构。\n\n## 核心要点\n\n- 自注意力机制\n- 多头注意力\n\n## 相关页面\n\n- [[Attention]] — 注意力机制\n\n## 来源\n\n- [论文](../sources/paper1.pdf)\n\n## 变更日志\n\n- 2026-04-10: 初始创建", ["AI/ML", "NLP"]),
            ("Attention", "注意力机制允许模型在处理序列时聚焦于相关部分。\n\n## 核心要点\n\n- Query, Key, Value\n\n## 相关页面\n\n- [[Transformer]] — 基于注意力的架构\n\n## 来源\n\n- [论文](../sources/paper2.pdf)\n\n## 变更日志\n\n- 2026-04-10: 初始创建", ["AI/ML"]),
            ("LoRA", "LoRA 是一种参数高效的微调方法。\n\n## 核心要点\n\n- 低秩适应\n- 参数效率\n\n## 相关页面\n\n- [[Fine-tuning]] — 全量微调\n\n## 来源\n\n- [论文](../sources/paper3.pdf)\n\n## 变更日志\n\n- 2026-04-10: 初始创建", ["AI/ML", "Fine-tuning"]),
            ("Fine-tuning", "全量微调是更新预训练模型所有参数的方法。\n\n## 核心要点\n\n- 全部参数更新\n\n## 相关页面\n\n- [[LoRA]] — 参数高效微调\n\n## 来源\n\n- [论文](../sources/paper4.pdf)\n\n## 变更日志\n\n- 2026-04-10: 初始创建", ["AI/ML", "Fine-tuning"]),
        ]

        for title, content, tags in pages:
            wiki.create_page(
                title,
                content,
                {"created": "2026-04-10", "updated": "2026-04-10", "tags": tags, "status": "active"},
            )

        return wiki

    def test_find_related_empty_wiki(self, temp_wiki):
        linker = KnowledgeLinker(temp_wiki)
        results = linker.find_related("Transformer")
        assert results == []

    def test_find_related_by_title_match(self, populated_wiki):
        linker = KnowledgeLinker(populated_wiki)
        results = linker.find_related("Transformer Architecture", query_tags=["AI/ML"])

        # 应该找到 Transformer 页面（标题包含关系 → CONTRASTS）
        transformer_rel = next((r for r in results if r.target == "Transformer"), None)
        assert transformer_rel is not None
        assert transformer_rel.score > 0.3
        assert transformer_rel.relation_type == RelationType.CONTRASTS

    def test_find_related_by_tag_match(self, populated_wiki):
        linker = KnowledgeLinker(populated_wiki)
        # 使用与 LoRA 完全相同的标签，确保高分匹配
        results = linker.find_related(
            "New Parameter-Efficient Method",
            query_tags=["AI/ML", "Fine-tuning"],
            min_score=0.05,  # 降低阈值使纯标签匹配能被收录
        )

        # 应该找到共享标签的页面
        titles = [r.target for r in results]
        assert "LoRA" in titles or "Fine-tuning" in titles

    def test_find_related_link_proximity(self, populated_wiki):
        linker = KnowledgeLinker(populated_wiki)
        # Attention 页面链接到 Transformer
        results = linker.find_related(
            "Self-Attention Mechanism",
            query_content="This is about [[Attention]] and its variants.",
            query_tags=["AI/ML"],
            min_score=0.05,  # 降低阈值使 link proximity 能被收录
        )

        # 通过 link proximity 应该找到 Transformer（或 Attention 自身）
        titles = [r.target for r in results]
        assert "Transformer" in titles or "Attention" in titles

    def test_classify_relation_updates(self, populated_wiki):
        linker = KnowledgeLinker(populated_wiki)
        transformer = populated_wiki.get_page("Transformer")
        attention = populated_wiki.get_page("Attention")

        # 标题相似度高的
        rel_type = linker.classify_relation(transformer, attention)
        # Transformer 和 Attention 标题差异大，应该不是 UPDATES
        assert rel_type != RelationType.UPDATES

    def test_classify_relation_contrasts(self, populated_wiki):
        linker = KnowledgeLinker(populated_wiki)
        lora = populated_wiki.get_page("LoRA")

        # 构造一个对比标题的页面（标题包含目标标题）
        fake_page = WikiPage(
            title="LoRA vs Fine-tuning",
            content="对比两种微调方法。",
            frontmatter={"tags": ["AI/ML"]},
            path=populated_wiki.wiki_dir / "test.md",
        )

        rel_type = linker.classify_relation(fake_page, lora)
        assert rel_type == RelationType.CONTRASTS

    def test_classify_relation_not_contrasts(self, populated_wiki):
        linker = KnowledgeLinker(populated_wiki)
        lora = populated_wiki.get_page("LoRA")

        # 标题不包含目标标题，不应触发 CONTRASTS
        fake_page = WikiPage(
            title="BitFit",
            content="BitFit 是另一种参数高效微调方法。",
            frontmatter={"tags": ["AI/ML", "Fine-tuning"]},
            path=populated_wiki.wiki_dir / "test.md",
        )

        rel_type = linker.classify_relation(fake_page, lora)
        # "bitfit" 不包含 "lora"，编辑距离 >= 3，不是 CONTRASTS
        assert rel_type != RelationType.CONTRASTS

    def test_classify_relation_extends(self, populated_wiki):
        linker = KnowledgeLinker(populated_wiki)
        transformer = populated_wiki.get_page("Transformer")

        # 构造一个扩展页面（共享多标签 + 内容相似）
        # 注意：标题不能包含目标标题，否则会先触发 CONTRASTS
        fake_page = WikiPage(
            title="XL-Attention",
            content="Transformer 是一种基于注意力机制的序列建模架构。XL-Attention 扩展了 Transformer，增加了片段级递归机制。",
            frontmatter={"tags": ["AI/ML", "NLP"]},
            path=populated_wiki.wiki_dir / "test.md",
        )

        rel_type = linker.classify_relation(fake_page, transformer, content_similarity=0.5)
        assert rel_type == RelationType.EXTENDS

    def test_build_relation_graph(self, populated_wiki):
        linker = KnowledgeLinker(populated_wiki)
        # 使用 deep 模式 + 降低阈值，确保能发现 Fine-tuning
        graph = linker.build_relation_graph(["LoRA"], mode="deep", min_score=0.1)

        # 应该找到 Fine-tuning（共享标签 + 互链）
        lora_rels = graph.by_source("LoRA")
        assert len(lora_rels) > 0
        titles = [r.target for r in lora_rels]
        assert "Fine-tuning" in titles

    def test_relation_graph_to_markdown(self, populated_wiki):
        linker = KnowledgeLinker(populated_wiki)
        graph = linker.build_relation_graph(["LoRA"], mode="light")

        md = graph.to_markdown()
        assert "# 关联报告" in md
        assert "LoRA" in md
        assert "Fine-tuning" in md

    def test_suggest_action(self, populated_wiki):
        linker = KnowledgeLinker(populated_wiki)
        suggestion = linker._suggest_action(RelationType.EXTENDS, "NewPage", "OldPage")
        assert "OldPage" in suggestion
        assert "NewPage" in suggestion


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
