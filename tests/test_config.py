"""Tests for llm_wiki.config."""

from llm_wiki.config import load_config


def test_depth_lint_defaults(tmp_path):
    config = load_config(tmp_path)
    depth = config["lint"]["depth"]
    assert depth["enabled"] is True
    assert depth["min_knowledge_chars"] == 500
    assert depth["skip_tags"] == ["QRF"]


def test_depth_lint_override_preserves_unspecified_defaults(tmp_path):
    (tmp_path / "config.yaml").write_text(
        """lint:
  depth:
    min_knowledge_chars: 900
    skip_tags:
      - QRF
      - Summary
""",
        encoding="utf-8",
    )
    depth = load_config(tmp_path)["lint"]["depth"]
    assert depth["min_knowledge_chars"] == 900
    assert depth["skip_tags"] == ["QRF", "Summary"]
    assert depth["min_meaningful_paragraphs"] == 3
    assert depth["compression_ratio_warning"] == 0.01
