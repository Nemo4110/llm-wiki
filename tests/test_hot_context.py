"""
Tests for wiki/hot.md - bounded recent-activity context
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from llm_wiki.core import WikiManager


@pytest.fixture
def wiki(tmp_path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    return WikiManager(wiki_dir)


class TestRecordActivity:
    def test_creates_hot_file_on_first_entry(self, wiki):
        wiki.record_activity("ingest | NewPage", ["wiki/NewPage.md", "log.md"])

        hot = wiki.wiki_dir / "hot.md"
        assert hot.exists()
        text = hot.read_text(encoding="utf-8")
        assert "ingest | NewPage" in text
        assert "wiki/NewPage.md" in text

    def test_newest_entry_first(self, wiki):
        wiki.record_activity("first", ["wiki/A.md"])
        wiki.record_activity("second", ["wiki/B.md"])

        text = (wiki.wiki_dir / "hot.md").read_text(encoding="utf-8")
        assert text.index("second") < text.index("first")

    def test_bounded_to_max_entries(self, wiki):
        for i in range(25):
            wiki.record_activity(f"entry-{i:02d}", [f"wiki/P{i}.md"])

        text = (wiki.wiki_dir / "hot.md").read_text(encoding="utf-8")
        assert "entry-24" in text           # 最新保留
        assert "entry-05" in text           # 第 20 条仍在
        assert "entry-04" not in text       # 超出边界被截断

    def test_existing_knowledge_body_preserved(self, wiki):
        # hot.md 头部说明之后的条目区被替换,头部保留
        hot = wiki.wiki_dir / "hot.md"
        hot.write_text("# Hot Context\n\n> 自定义说明,不应被覆盖。\n", encoding="utf-8")
        wiki.record_activity("new entry", ["wiki/X.md"])

        text = hot.read_text(encoding="utf-8")
        assert "自定义说明" in text
        assert "new entry" in text


class TestHotNotAKnowledgePage:
    def test_hot_md_excluded_from_page_listing(self, wiki):
        wiki.create_page("Real", "# Real\n\n内容。\n", {"status": "active"})
        wiki.record_activity("x", ["wiki/Real.md"])

        titles = [p.title for p in wiki.list_pages()]
        assert "Real" in titles
        assert "hot" not in [t.lower() for t in titles]
