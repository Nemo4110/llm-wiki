"""
Tests for llm_wiki.core — WikiManager, WikiPage, and helpers.

Run individually:
    pytest tests/test_core.py -v
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from llm_wiki.core import WikiManager, WikiPage, find_wiki_root, IngestResult


class TestWikiPage:
    def test_links_extraction(self):
        page = WikiPage(
            title="Test",
            content="See [[LoRA]] and [[Transformer|TF]] for details.",
            frontmatter={},
            path=Path("test.md"),
        )
        # links property extracts raw bracket content including pipe aliases
        assert page.links == {"LoRA", "Transformer|TF"}

    def test_status_defaults_to_draft(self):
        page = WikiPage(title="T", content="", frontmatter={}, path=Path("t.md"))
        assert page.status == "draft"

    def test_tags_defaults_to_empty(self):
        page = WikiPage(title="T", content="", frontmatter={}, path=Path("t.md"))
        assert page.tags == []

    def test_content_hash_deterministic(self):
        page = WikiPage(
            title="T",
            content="body",
            frontmatter={"tags": ["a"]},
            path=Path("t.md"),
        )
        h1 = page.content_hash
        h2 = page.content_hash
        assert h1 == h2
        assert len(h1) == 64  # sha256 hex


class TestWikiManagerListPages:
    def test_list_pages_excludes_index(self, wiki_manager):
        pages = wiki_manager.list_pages()
        titles = [p.title for p in pages]
        assert "index" not in titles
        assert "Transformer" in titles
        assert "LoRA" in titles
        assert "Docker" in titles

    def test_list_pages_returns_wiki_page_objects(self, wiki_manager):
        pages = wiki_manager.list_pages()
        assert all(isinstance(p, WikiPage) for p in pages)


class TestWikiManagerGetPage:
    def test_get_page_found(self, wiki_manager):
        page = wiki_manager.get_page("Transformer")
        assert page is not None
        assert page.title == "Transformer"

    def test_get_page_not_found(self, wiki_manager):
        assert wiki_manager.get_page("NonExistent") is None

    def test_get_page_variations(self, temp_wiki_root, wiki_manager):
        # Create a page with spaces in title
        (temp_wiki_root / "wiki" / "My Page.md").write_text(
            "---\ncreated: \"2026-04-01\"\n---\n\n# My Page\n\ncontent",
            encoding="utf-8",
        )
        assert wiki_manager.get_page("My Page") is not None


class TestWikiManagerCreatePage:
    def test_create_page_writes_file(self, temp_wiki_root, wiki_manager):
        path = wiki_manager.create_page(
            "NewConcept",
            "# NewConcept\n\nA new idea.",
            {"created": "2026-04-20", "tags": ["Test"], "status": "active"},
        )
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "NewConcept" in text
        assert "Test" in text

    def test_create_page_sanitizes_filename(self, temp_wiki_root, wiki_manager):
        path = wiki_manager.create_page(
            "A/B Test",
            "# A/B Test\n\ncontent",
            {"created": "2026-04-20", "status": "active"},
        )
        # Both '/' and ' ' are replaced with '-'
        assert path.name == "A-B-Test.md"


class TestWikiManagerUpdatePage:
    def test_update_page_replace(self, wiki_manager):
        wiki_manager.create_page(
            "Updatable",
            "# Updatable\n\nold content",
            {"created": "2026-04-01", "status": "active"},
        )
        wiki_manager.update_page("Updatable", "# Updatable\n\nnew content", merge_strategy="replace")
        page = wiki_manager.get_page("Updatable")
        assert "new content" in page.content
        assert "old content" not in page.content
        assert page.frontmatter["updated"] == datetime.now().strftime("%Y-%m-%d")

    def test_update_page_append(self, wiki_manager):
        wiki_manager.create_page(
            "Appendable",
            "# Appendable\n\nbase content",
            {"created": "2026-04-01", "status": "active"},
        )
        wiki_manager.update_page("Appendable", "extra content", merge_strategy="append")
        page = wiki_manager.get_page("Appendable")
        assert "base content" in page.content
        assert "extra content" in page.content

    def test_update_page_not_found_raises(self, wiki_manager):
        with pytest.raises(ValueError, match="Page not found"):
            wiki_manager.update_page("Missing", "content")


class TestWikiManagerLint:
    def test_lint_finds_orphans(self, temp_wiki_root, wiki_manager):
        # Add a page that nobody links to
        wiki_manager.create_page(
            "Orphan",
            "# Orphan\n\nNo one links here.",
            {"created": "2026-04-01", "status": "active"},
        )
        issues = wiki_manager.lint()
        assert "Orphan" in issues["orphans"]

    def test_lint_finds_dead_links(self, wiki_manager):
        # Create a page with a dead link
        wiki_manager.create_page(
            "DeadLinkPage",
            "# DeadLinkPage\n\nSee [[NonExistent]] for details.",
            {"created": "2026-04-01", "status": "active"},
        )
        issues = wiki_manager.lint()
        assert "NonExistent" in issues["dead_links"]

    def test_lint_finds_stale_pages(self, temp_wiki_root, wiki_manager):
        stale_date = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
        wiki_manager.create_page(
            "StalePage",
            "# StalePage\n\nOld info.",
            {"created": "2025-01-01", "updated": stale_date, "status": "active"},
        )
        issues = wiki_manager.lint()
        assert "StalePage" in issues["stale"]

    def test_lint_finds_drafts(self, temp_wiki_root, wiki_manager):
        wiki_manager.create_page(
            "DraftPage",
            "# DraftPage\n\nWork in progress.",
            {"created": "2026-04-01", "status": "draft"},
        )
        issues = wiki_manager.lint()
        assert "DraftPage" in issues["drafts"]

    def test_lint_no_issues_on_healthy_wiki(self, temp_wiki_root, wiki_manager):
        # Remove dead links from sample data by creating stub for Attention
        wiki_manager.create_page(
            "Attention",
            "# Attention\n\nAttention mechanism.",
            {"created": "2026-04-01", "status": "active"},
        )
        issues = wiki_manager.lint()
        # Orphans may still exist (Docker is not linked), but dead_links should be empty
        assert issues["dead_links"] == []


class TestWikiManagerLog:
    def test_append_and_read_log(self, wiki_manager):
        wiki_manager.append_log("test", "description", ["detail 1", "detail 2"])
        entries = wiki_manager.read_log(5)
        assert any("test" in e and "description" in e for e in entries)

    def test_read_log_empty(self, temp_wiki_root):
        # Fresh wiki with no log.md
        wm = WikiManager(temp_wiki_root / "wiki")
        assert wm.read_log(5) == []


class TestFindWikiRoot:
    def test_finds_root_with_claude_md(self, temp_wiki_root):
        root = find_wiki_root(temp_wiki_root)
        assert root == temp_wiki_root

    def test_returns_none_when_missing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            assert find_wiki_root(Path(td)) is None


class TestIngestResult:
    def test_defaults(self):
        r = IngestResult(source="paper.pdf")
        assert r.new_pages == []
        assert r.updated_pages == []
        assert r.insights == []
