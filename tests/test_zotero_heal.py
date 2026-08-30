"""Tests for the P1 stale-item-key healing pipeline (zotero-heal)."""

from pathlib import Path

import yaml

from src.llm_wiki.zotero_heal import (
    apply_heal_plan,
    plan_heal,
    plan_to_heal_manifest,
)
from src.llm_wiki.zotero_plan import SnapshotItem, ZoteroBinding


def _binding(item_key="DEAD0001", doi="", citation_key="", source_title="Deep Learning Paper",
             page_stem="Deep-Learning-Paper"):
    return ZoteroBinding(
        item_key=item_key,
        page_stem=page_stem,
        page_title=page_stem.replace("-", " "),
        source_title=source_title,
        source_type="academic_paper",
        page_active=True,
        ingest_complete=True,
        doi=doi,
        citation_key=citation_key,
    )


def _item(item_key, title="Deep Learning Paper", doi="", citation_key=""):
    return SnapshotItem(
        item_key=item_key,
        title=title,
        item_type="journalArticle",
        doi=doi,
        citation_key=citation_key,
    )


class TestPlanHeal:
    def test_live_binding_is_not_stale(self):
        plan = plan_heal([_binding(item_key="LIVE0001")], [_item("LIVE0001")])
        assert plan.stale == ()

    def test_stale_binding_matched_by_doi(self):
        binding = _binding(doi="10.1000/xyz")
        item = _item("NEW00001", doi="https://doi.org/10.1000/xyz")
        plan = plan_heal([binding], [item])
        assert len(plan.stale) == 1
        candidate = plan.stale[0]
        assert candidate.matched_by == "doi"
        assert candidate.new_item_key == "NEW00001"

    def test_stale_binding_matched_by_citation_key(self):
        binding = _binding(citation_key="author2024deep")
        item = _item("NEW00002", citation_key="author2024deep")
        plan = plan_heal([binding], [item])
        assert plan.stale[0].matched_by == "citation_key"
        assert plan.stale[0].new_item_key == "NEW00002"

    def test_stale_binding_matched_by_normalized_title(self):
        binding = _binding(source_title="Deep Learning: A Paper!")
        item = _item("NEW00003", title="deep learning a paper")
        plan = plan_heal([binding], [item])
        assert plan.stale[0].matched_by == "title"
        assert plan.stale[0].new_item_key == "NEW00003"

    def test_doi_wins_over_title(self):
        binding = _binding(doi="10.1000/xyz", source_title="Deep Learning Paper")
        by_title = _item("NEW0000A", title="Deep Learning Paper")
        by_doi = _item("NEW0000B", title="Other Title", doi="10.1000/xyz")
        plan = plan_heal([binding], [by_title, by_doi])
        assert plan.stale[0].matched_by == "doi"
        assert plan.stale[0].new_item_key == "NEW0000B"

    def test_ambiguous_doi_stays_unmatched(self):
        binding = _binding(doi="10.1000/xyz")
        items = [_item("NEW0000C", doi="10.1000/xyz"), _item("NEW0000D", doi="10.1000/xyz")]
        plan = plan_heal([binding], items)
        assert plan.stale[0].matched_by == ""
        assert plan.stale[0].new_item_key == ""

    def test_no_candidate_stays_unmatched(self):
        plan = plan_heal([_binding()], [])
        assert plan.stale[0].matched_by == ""

    def test_manifest_is_review_only_versioned(self):
        binding = _binding(doi="10.1000/xyz")
        plan = plan_heal([binding], [_item("NEW00001", doi="10.1000/xyz")])
        manifest = plan_to_heal_manifest(plan)
        assert manifest["version"] == 1
        assert manifest["mode"] == "review-only"
        assert manifest["stale"][0]["new_item_key"] == "NEW00001"


class TestApplyHealPlan:
    def _make_bound_page(self, wiki_manager, old_key="DEAD0001"):
        frontmatter = {
            "created": "2026-01-01",
            "updated": "2026-01-01",
            "status": "active",
            "sources_meta": [
                {
                    "title": "Deep Learning Paper",
                    "type": "academic_paper",
                    "zotero_item_key": old_key,
                }
            ],
        }
        return wiki_manager.create_page(
            "Deep Learning Paper", "# Deep Learning Paper\n\nbody text\n", frontmatter
        )

    def test_apply_rebinds_frontmatter_in_place(self, wiki_manager):
        path = self._make_bound_page(wiki_manager)
        plan = plan_heal(
            [_binding()], [_item("NEW00001")],  # title match fallback
        )
        changed = apply_heal_plan(wiki_manager, plan)

        assert changed == [path]
        text = path.read_text(encoding="utf-8")
        assert "NEW00001" in text
        assert "DEAD0001" not in text
        # 文件名不变(frontmatter 原地更新,不重命名)
        assert path.name == "Deep-Learning-Paper.md"

    def test_apply_skips_unmatched(self, wiki_manager):
        path = self._make_bound_page(wiki_manager)
        plan = plan_heal([_binding()], [])
        changed = apply_heal_plan(wiki_manager, plan)
        assert changed == []
        assert "DEAD0001" in path.read_text(encoding="utf-8")

    def test_apply_appends_log(self, wiki_manager):
        self._make_bound_page(wiki_manager)
        plan = plan_heal([_binding()], [_item("NEW00001")])
        apply_heal_plan(wiki_manager, plan)
        log_text = wiki_manager.log_file.read_text(encoding="utf-8")
        assert "zotero-heal" in log_text
        assert "NEW00001" in log_text
