"""
Tests for bm25.py - deterministic local BM25 ranking
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from llm_wiki.bm25 import BM25, tokenize


class TestTokenize:
    """中英文混合分词:英文按词,中文按单字+二字滑窗"""

    def test_english_words_lowercased(self):
        tokens = tokenize("LoRA uses Low-Rank Adaptation")
        assert "lora" in tokens
        assert "rank" in tokens
        assert "LoRA" not in tokens

    def test_chinese_unigrams_and_bigrams(self):
        tokens = tokenize("低秩适应")
        assert "低" in tokens
        assert "秩" in tokens
        assert "低秩" in tokens
        assert "秩适" in tokens

    def test_stop_words_removed(self):
        tokens = tokenize("the model is a system")
        assert "the" not in tokens
        assert "is" not in tokens
        assert "model" in tokens

    def test_deterministic(self):
        assert tokenize("混合 Mixed 输入 Input") == tokenize("混合 Mixed 输入 Input")


class TestBM25Ranking:
    """BM25 排序行为"""

    @pytest.fixture
    def corpus(self):
        docs = [
            tokenize("LoRA low-rank adaptation for fine-tuning large language models 低秩 适应 微调"),
            tokenize("Transformer self-attention mechanism for sequence modeling 注意力 机制"),
            tokenize("Docker container image registry deployment 容器 部署"),
        ]
        return BM25(docs)

    def test_topical_query_ranks_relevant_doc_first(self, corpus):
        scores = corpus.scores(tokenize("LoRA fine-tuning 微调"))
        assert scores[0] == max(scores)
        assert scores[0] > scores[2]

    def test_rare_term_dominates(self, corpus):
        # "registry" 只出现在 doc 3,比普遍词更能区分
        scores = corpus.scores(tokenize("registry"))
        assert scores[2] == max(scores)
        assert scores[0] == 0.0
        assert scores[1] == 0.0

    def test_unknown_terms_score_zero(self, corpus):
        scores = corpus.scores(tokenize("kubernetes prometheus"))
        assert scores == [0.0, 0.0, 0.0]

    def test_scores_non_negative_and_deterministic(self, corpus):
        q = tokenize("attention 注意力")
        first = corpus.scores(q)
        second = corpus.scores(q)
        assert first == second
        assert all(s >= 0.0 for s in first)

    def test_empty_corpus(self):
        assert BM25([]).scores(tokenize("anything")) == []
