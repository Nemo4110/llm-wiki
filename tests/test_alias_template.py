"""Tests for the alias wildcard template engine (方案五, alias-only scope)."""

import pytest

from llm_wiki.alias_template import render_alias_template


class TestWildcards:
    def test_title_is_sanitized(self):
        alias = render_alias_template("%t", {"title": "LoRA: Low-Rank Adaptation"})
        assert alias == "LoRA-Low-Rank-Adaptation"

    def test_collection_hierarchy_sanitized_per_segment(self):
        alias = render_alias_template(
            "%c/%t",
            {"collection_path": "Machine Learning/LLM", "title": "FlashAttention"},
        )
        assert alias == "Machine-Learning/LLM/FlashAttention"

    def test_full_pattern(self):
        alias = render_alias_template(
            "%c/%y-%a-%t",
            {
                "collection_path": "papers",
                "year": "2024",
                "author": "hu",
                "title": "LoRA",
            },
        )
        assert alias == "papers/2024-hu-LoRA"

    def test_citekey_and_item_type(self):
        alias = render_alias_template(
            "%b-%T", {"citekey": "hu2021lora", "item_type": "journalArticle"}
        )
        assert alias == "hu2021lora-journalArticle"

    def test_cjk_title_preserved(self):
        alias = render_alias_template("%t", {"title": "深入理解 大模型"})
        assert alias == "深入理解-大模型"

    def test_percent_escape(self):
        alias = render_alias_template("100%%-%t", {"title": "coverage"})
        assert alias == "100%-coverage"


class TestRobustness:
    def test_unknown_wildcard_rejected(self):
        with pytest.raises(ValueError, match="wildcard"):
            render_alias_template("%z-%t", {"title": "x"})

    def test_empty_fields_collapse_separators(self):
        alias = render_alias_template("%y-%a-%t", {"title": "Only Title"})
        assert alias == "Only-Title"

    def test_empty_collection_segment_dropped(self):
        alias = render_alias_template(
            "%c/%t", {"collection_path": "", "title": "Paper"}
        )
        assert alias == "Paper"

    def test_result_is_relative_and_safe(self):
        alias = render_alias_template("/%t/", {"title": "paper"})
        assert alias == "paper"
        assert not alias.startswith("/")

    def test_missing_context_values_are_empty(self):
        alias = render_alias_template("%t", {})
        assert alias == "untitled"  # sanitize fallback
