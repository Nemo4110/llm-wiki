from pathlib import Path

import pytest

from llm_wiki.depth_lint import DepthLintConfig, analyze_depth, extract_knowledge_body


def _config(**overrides):
    values = {
        "enabled": True,
        "min_knowledge_chars": 500,
        "min_meaningful_paragraphs": 3,
        "multi_source_threshold": 3,
        "multi_source_min_knowledge_chars": 800,
        "source_volume_threshold": 10_000,
        "compression_ratio_warning": 0.01,
        "extreme_source_volume_threshold": 20_000,
        "extreme_compression_max_knowledge_chars": 1_500,
        "skip_tags": ("QRF",),
    }
    values.update(overrides)
    return DepthLintConfig(**values)


def test_extract_knowledge_body_excludes_boilerplate_sections():
    content = """# Topic

A substantive introduction explaining the mechanism in enough detail to count.

## Mechanism

The model transforms input state into a ranked decision through a verified pipeline.

## 相关页面

- [[Other]] — related

## 来源

- [Source](../sources/source.md)

## 变更日志

- 2026-07-25: updated
"""
    knowledge = extract_knowledge_body(content)
    assert "transforms input state" in knowledge
    assert "Other" not in knowledge
    assert "source.md" not in knowledge
    assert "2026-07-25" not in knowledge


def test_extract_knowledge_body_normalizes_markdown():
    content = """# Topic

**Important concept** uses [[Canonical-Page|display text]] and [external label](https://example.com).
"""
    knowledge = extract_knowledge_body(content)
    assert "Important concept" in knowledge
    assert "display text" in knowledge
    assert "external label" in knowledge
    assert "[[" not in knowledge
    assert "https://" not in knowledge


def test_short_active_page_is_flagged(tmp_path):
    issue = analyze_depth(
        page_title="Short",
        page_stem="Short",
        content="# Short\n\nOnly one tiny statement.",
        frontmatter={"status": "active", "sources": []},
        project_root=tmp_path,
        config=_config(),
    )
    assert issue is not None
    assert "short-knowledge-body" in issue.reasons


def test_many_large_sources_with_tiny_synthesis_are_flagged(tmp_path):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    sources = []
    for index in range(3):
        path = source_dir / f"source-{index}.md"
        path.write_text("mechanism and evidence " * 400, encoding="utf-8")
        sources.append(path.relative_to(tmp_path).as_posix())
    issue = analyze_depth(
        page_title="Compressed",
        page_stem="Compressed",
        content="# Compressed\n\nA tiny synthesis that omits almost everything.",
        frontmatter={"status": "active", "sources": sources},
        project_root=tmp_path,
        config=_config(),
    )
    assert issue is not None
    assert "multi-source-underdeveloped" in issue.reasons
    assert "extreme-compression" in issue.reasons
    assert issue.metrics.local_source_chars > 10_000


def test_adequate_page_is_not_flagged(tmp_path):
    paragraphs = [
        "This paragraph explains a concrete mechanism, its input state, transformation, and output behavior in detail.",
        "This paragraph preserves quantitative evidence, evaluation conditions, and the boundary under which the result holds.",
        "This paragraph compares alternatives by latency, accuracy, maintenance cost, and operational risk.",
        "This paragraph records failure modes and gives a concrete decision rule for choosing the method.",
        "This paragraph explains the implementation procedure and how the final result should be verified.",
        "This paragraph records open questions and prevents source opinion from becoming an unconditional fact.",
    ]
    content = "# Developed\n\n## Mechanism\n\n" + "\n\n".join(paragraphs)
    issue = analyze_depth(
        page_title="Developed",
        page_stem="Developed",
        content=content,
        frontmatter={"status": "active", "sources": []},
        project_root=tmp_path,
        config=_config(),
    )
    assert issue is None


def test_qrf_tag_is_skipped(tmp_path):
    issue = analyze_depth(
        page_title="Q",
        page_stem="Q",
        content="# Q\n\nshort",
        frontmatter={"status": "active", "tags": ["QRF"]},
        project_root=tmp_path,
        config=_config(),
    )
    assert issue is None


def test_frontmatter_skip_is_respected(tmp_path):
    issue = analyze_depth(
        page_title="S",
        page_stem="S",
        content="# S\n\nshort",
        frontmatter={"status": "active", "lint_depth": "skip"},
        project_root=tmp_path,
        config=_config(),
    )
    assert issue is None


def test_draft_is_skipped(tmp_path):
    issue = analyze_depth(
        page_title="D",
        page_stem="D",
        content="# D\n\nshort",
        frontmatter={"status": "draft"},
        project_root=tmp_path,
        config=_config(),
    )
    assert issue is None


def test_missing_binary_and_parent_sources_do_not_crash(tmp_path):
    binary = tmp_path / "sources" / "artifact.pdf"
    binary.parent.mkdir()
    binary.write_bytes(b"%PDF-binary")
    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside.write_text("secret material" * 100, encoding="utf-8")
    issue = analyze_depth(
        page_title="Safe",
        page_stem="Safe",
        content="# Safe\n\nshort",
        frontmatter={
            "status": "active",
            "sources": ["sources/missing.md", "sources/artifact.pdf", "../outside.md"],
        },
        project_root=tmp_path,
        config=_config(),
    )
    assert issue is not None
    assert issue.metrics.local_source_chars == 0


def test_depth_issue_exposes_structured_details(tmp_path):
    issue = analyze_depth(
        page_title="Thin Page",
        page_stem="Thin-Page",
        content="# Thin Page\n\nOnly a tiny summary.",
        frontmatter={"status": "active", "sources": []},
        project_root=tmp_path,
        config=_config(),
    )

    assert issue is not None
    details = issue.to_dict()
    assert details["page_title"] == "Thin Page"
    assert details["page_stem"] == "Thin-Page"
    assert details["knowledge_chars"] == issue.metrics.knowledge_chars
    assert details["meaningful_paragraphs"] == issue.metrics.meaningful_paragraphs
    assert details["substantive_sections"] == issue.metrics.substantive_sections
    assert details["source_count"] == 0
    assert details["local_source_chars"] == 0
    assert details["compression_ratio"] is None
    assert details["reasons"] == list(issue.reasons)


def test_symlinked_source_is_counted(tmp_path):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside.write_text("sensitive external material" * 100, encoding="utf-8")
    symlink = source_dir / "escape.md"
    try:
        symlink.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"Symlink creation is unavailable: {exc}")

    issue = analyze_depth(
        page_title="Safe",
        page_stem="Safe",
        content="# Safe\n\nshort",
        frontmatter={"status": "active", "sources": ["sources/escape.md"]},
        project_root=tmp_path,
        config=_config(),
    )

    assert issue is not None
    assert issue.metrics.local_source_chars == len(
        "sensitive external material" * 100
    )
