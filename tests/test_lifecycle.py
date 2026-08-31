"""
Tests for note lifecycle: seed -> developing -> mature -> evergreen
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


from llm_wiki.core import LIFECYCLE_STATES, WikiManager


def _make_wiki(tmp_path, pages):
    """pages: list of (title, body, status)"""
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    wiki = WikiManager(wiki_dir)
    for title, body, status in pages:
        wiki.create_page(
            title,
            body,
            {
                "created": "2026-08-01",
                "updated": "2026-08-01",
                "tags": ["test"],
                "status": status,
            },
        )
    return wiki


class TestLifecycleVocabulary:
    def test_lifecycle_states_defined(self):
        assert LIFECYCLE_STATES == ("seed", "developing", "mature", "evergreen")


class TestLintLifecycle:
    def test_mature_but_shallow_is_mismatch(self, tmp_path):
        wiki = _make_wiki(tmp_path, [("Thin", "# Thin\n\n一句话。\n", "mature")])
        issues = wiki.lint()
        assert any("Thin" in m for m in issues["lifecycle_mismatch"])

    def test_evergreen_but_shallow_is_mismatch(self, tmp_path):
        wiki = _make_wiki(tmp_path, [("Thin", "# Thin\n\n一句话。\n", "evergreen")])
        issues = wiki.lint()
        assert any("Thin" in m for m in issues["lifecycle_mismatch"])

    def test_developing_shallow_is_not_mismatch(self, tmp_path):
        # developing 页面允许浅——它还在成长
        wiki = _make_wiki(
            tmp_path, [("Growing", "# Growing\n\n一句话。\n", "developing")]
        )
        issues = wiki.lint()
        assert issues["lifecycle_mismatch"] == []

    def test_mature_with_substance_is_not_mismatch(self, tmp_path):
        body = "# Deep\n\n" + "\n\n".join(
            f"## 章节{i}\n\n" + "这是一段有实质内容的段落,包含机制解释与证据。" * 12
            for i in range(4)
        )
        wiki = _make_wiki(tmp_path, [("Deep", body, "mature")])
        issues = wiki.lint()
        assert issues["lifecycle_mismatch"] == []

    def test_unknown_status_flagged(self, tmp_path):
        wiki = _make_wiki(tmp_path, [("Weird", "# Weird\n\n内容。\n", "publised")])
        issues = wiki.lint()
        assert any("Weird" in m and "publised" in m for m in issues["invalid_status"])

    def test_legacy_statuses_accepted(self, tmp_path):
        wiki = _make_wiki(
            tmp_path,
            [
                ("A", "# A\n\n内容。\n", "draft"),
                ("B", "# B\n\n内容。\n", "active"),
                ("C", "# C\n\n内容。\n", "archived"),
            ],
        )
        issues = wiki.lint()
        assert issues["invalid_status"] == []
