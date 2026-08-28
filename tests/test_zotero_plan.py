from pathlib import Path

import pytest

from src.llm_wiki.core import WikiManager
from src.llm_wiki.zotero_plan import (
    build_zotero_plan,
    collect_zotero_bindings,
    extract_doi_from_text,
    load_snapshot,
    normalize_doi,
    plan_to_manifest,
    SnapshotItem,
)


def _write_page(
    wiki_dir: Path,
    stem: str,
    *,
    item_key: str,
    title: str,
    coverage_verified: bool = True,
    status: str = "active",
    doi: str = "",
):
    doi_field = f', doi: "{doi}"' if doi else ""
    wiki_dir.mkdir(parents=True, exist_ok=True)
    (wiki_dir / f"{stem}.md").write_text(
        f'''---
created: 2026-08-23
updated: 2026-08-23
sources: []
source_types:
  - "academic_paper"
sources_meta:
  - {{title: "{title}", type: "academic_paper", zotero_item_key: "{item_key}", library_id: "0"{doi_field}}}
tags:
  - "AI/ML"
coverage_verified: {str(coverage_verified).lower()}
status: "{status}"
---

# {stem.replace('-', ' ')}

Knowledge body.
''',
        encoding="utf-8",
    )


def test_normalize_doi():
    assert normalize_doi("https://doi.org/10.1000/Test.1") == "10.1000/Test.1"
    assert normalize_doi("doi: 10.1000/test.2.") == "10.1000/test.2"
    assert normalize_doi(None) == ""
    assert extract_doi_from_text("https://doi.org/10.1000/test.3") == "10.1000/test.3"


def test_build_plan_combines_wiki_tags_and_collection_cleanup(tmp_path):
    wiki_dir = tmp_path / "wiki"
    _write_page(
        wiki_dir,
        "GNN-Foundations",
        item_key="ITEM0001",
        title="Graph Paper",
        doi="10.48550/arXiv.2401.00001",
    )
    _write_page(
        wiki_dir,
        "Old-Topic",
        item_key="ITEM0002",
        title="Other Paper",
    )

    snapshot = tmp_path / "gnn.yaml"
    snapshot.write_text(
        '''version: 1
library_id: "0"
collection:
  name: GNN
  key: A9VNJUPI
items:
  - item_key: ITEM0001
    title: Graph Paper
    item_type: preprint
    doi: 10.48550/arXiv.2401.00001
    tags:
      - GNN
      - llm-wiki:Old-Topic
''',
        encoding="utf-8",
    )

    wiki = WikiManager(wiki_dir)
    library_id, collection_name, collection_key, items = load_snapshot(snapshot)
    plan = build_zotero_plan(
        collect_zotero_bindings(wiki),
        items,
        library_id=library_id,
        collection_name=collection_name,
        collection_key=collection_key,
    )

    item = plan.items[0]
    assert item.desired_tags == frozenset(
        {"llm-wiki:GNN-Foundations", "llm-wiki:ingested"}
    )
    assert item.add_tags == item.desired_tags
    assert item.remove_candidates == frozenset({"GNN", "llm-wiki:Old-Topic"})
    assert item.doi_state == "arxiv-doi"
    assert "check preprint-to-publication relation" in item.actions


def test_unbound_snapshot_item_is_not_marked_ingested(tmp_path):
    wiki = WikiManager(tmp_path / "wiki")
    (tmp_path / "wiki").mkdir()
    snapshot = tmp_path / "gnn.yaml"
    snapshot.write_text(
        '''version: 1
library_id: "0"
collection:
  name: GNN
  key: A9VNJUPI
items:
  - item_key: ITEM0003
    title: Unbound Graph Paper
    item_type: conferencePaper
    tags: [GNN, important]
''',
        encoding="utf-8",
    )

    _, collection_name, collection_key, items = load_snapshot(snapshot)
    plan = build_zotero_plan(
        collect_zotero_bindings(wiki),
        items,
        collection_name=collection_name,
        collection_key=collection_key,
    )

    item = plan.items[0]
    assert item.desired_tags == frozenset()
    assert item.add_tags == frozenset()
    assert item.remove_candidates == frozenset({"GNN"})
    assert item.doi_state == "unknown"
    assert "not linked from wiki sources_meta" in item.actions


def test_missing_doi_is_distinct_from_unobserved_doi(tmp_path):
    snapshot = tmp_path / "items.yaml"
    snapshot.write_text(
        '''version: 1
collection:
  name: GNN
  key: A9VNJUPI
items:
  - item_key: MISSING1
    title: Missing DOI
    item_type: journalArticle
    doi: ""
  - item_key: UNKNOWN1
    title: Unknown DOI
    item_type: journalArticle
''',
        encoding="utf-8",
    )
    _, collection_name, collection_key, items = load_snapshot(snapshot)
    plan = build_zotero_plan(
        [],
        items,
        collection_name=collection_name,
        collection_key=collection_key,
    )

    assert [item.doi_state for item in plan.items] == ["missing", "unknown"]
    assert plan.items[0].actions[0] == "search DOI candidate"
    assert plan.items[1].actions[0] == "read DOI field from Zotero"


def test_load_snapshot_rejects_duplicate_keys(tmp_path):
    snapshot = tmp_path / "duplicate.yaml"
    snapshot.write_text(
        '''version: 1
collection: {name: GNN, key: A9VNJUPI}
items:
  - {item_key: DUPLICATE, title: One}
  - {item_key: DUPLICATE, title: Two}
''',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate snapshot item_key"):
        load_snapshot(snapshot)


def test_doi_url_conflict_is_reported(tmp_path):
    snapshot = tmp_path / "conflict.yaml"
    snapshot.write_text(
        """version: 1
collection: {name: GNN, key: A9VNJUPI}
items:
  - item_key: CONFLICT1
    title: Conflicting DOI
    item_type: journalArticle
    doi: 10.1145/example
    url: https://doi.org/10.1038/different
""",
        encoding="utf-8",
    )
    _, collection_name, collection_key, items = load_snapshot(snapshot)
    plan = build_zotero_plan(
        [], items, collection_name=collection_name, collection_key=collection_key
    )

    assert plan.items[0].doi_state == "conflict"
    assert "review DOI/URL conflict" in plan.items[0].actions


def test_wiki_doi_is_a_candidate_when_zotero_field_is_empty(tmp_path):
    wiki_dir = tmp_path / "wiki"
    _write_page(
        wiki_dir,
        "Graph-Models",
        item_key="WIKIDOI1",
        title="Graph DOI Paper",
        doi="10.1000/from-wiki",
    )
    snapshot = tmp_path / "wiki-doi.yaml"
    snapshot.write_text(
        """version: 1
collection: {name: GNN, key: A9VNJUPI}
items:
  - item_key: WIKIDOI1
    title: Graph DOI Paper
    item_type: conferencePaper
    doi: ""
""",
        encoding="utf-8",
    )
    _, collection_name, collection_key, items = load_snapshot(snapshot)
    plan = build_zotero_plan(
        collect_zotero_bindings(WikiManager(wiki_dir)),
        items,
        collection_name=collection_name,
        collection_key=collection_key,
    )

    assert plan.items[0].doi_state == "wiki-candidate"
    assert plan.items[0].doi == "10.1000/from-wiki"
    assert "verify DOI candidate from wiki provenance" in plan.items[0].actions


def test_unobserved_tags_do_not_create_write_plan(tmp_path):
    wiki_dir = tmp_path / "wiki"
    _write_page(
        wiki_dir,
        "Graph-Models",
        item_key="TAGUNKNOWN",
        title="Graph Tag Paper",
    )
    snapshot = tmp_path / "tag-unknown.yaml"
    snapshot.write_text(
        """version: 1
collection: {name: GNN, key: A9VNJUPI}
items:
  - item_key: TAGUNKNOWN
    title: Graph Tag Paper
    item_type: conferencePaper
    doi: ""
""",
        encoding="utf-8",
    )
    _, collection_name, collection_key, items = load_snapshot(snapshot)
    plan = build_zotero_plan(
        collect_zotero_bindings(WikiManager(wiki_dir)),
        items,
        collection_name=collection_name,
        collection_key=collection_key,
    )

    assert plan.items[0].desired_tags
    assert plan.items[0].add_tags == frozenset()
    assert plan.items[0].remove_candidates == frozenset()
    assert "read current tags from Zotero" in plan.items[0].actions


def test_same_title_preprint_and_published_items_create_relation_candidates(tmp_path):
    snapshot = tmp_path / "relations.yaml"
    snapshot.write_text(
        """version: 1
collection: {name: GNN, key: A9VNJUPI}
items:
  - item_key: PREPRINT1
    title: A Survey on Graphs
    item_type: preprint
    doi: ""
    tags: []
  - item_key: PUBLISHED1
    title: A Survey on Graphs
    item_type: journalArticle
    doi: 10.1000/published
    tags: []
""",
        encoding="utf-8",
    )
    _, collection_name, collection_key, items = load_snapshot(snapshot)
    plan = build_zotero_plan(
        [], items, collection_name=collection_name, collection_key=collection_key
    )

    by_key = {item.item_key: item for item in plan.items}
    assert by_key["PREPRINT1"].relation_candidates == ("PUBLISHED1",)
    assert by_key["PUBLISHED1"].relation_candidates == ("PREPRINT1",)
    assert "review same-title preprint/published relation" in by_key["PREPRINT1"].actions


def test_existing_relation_is_not_proposed_again(tmp_path):
    snapshot = tmp_path / "relations.yaml"
    snapshot.write_text(
        """version: 1
collection: {name: GNN, key: A9VNJUPI}
items:
  - item_key: PREPRINT1
    title: A Survey on Graphs
    item_type: preprint
    doi: ""
    tags: []
    related_items: [PUBLISHED1]
  - item_key: PUBLISHED1
    title: A Survey on Graphs
    item_type: journalArticle
    doi: 10.1000/published
    tags: []
    related_items: [PREPRINT1]
""",
        encoding="utf-8",
    )
    _, collection_name, collection_key, items = load_snapshot(snapshot)
    plan = build_zotero_plan(
        [], items, collection_name=collection_name, collection_key=collection_key
    )

    assert all(not item.relation_candidates for item in plan.items)


def test_manifest_contains_only_reviewable_mutations(tmp_path):
    snapshot = tmp_path / "manifest.yaml"
    snapshot.write_text(
        """version: 1
collection: {name: GNN, key: A9VNJUPI}
items:
  - item_key: ITEM1
    title: Needs Review
    item_type: conferencePaper
    doi: ""
    tags: [GNN]
  - item_key: ITEM2
    title: Already Stable
    item_type: conferencePaper
    doi: 10.1000/stable
    tags: []
""",
        encoding="utf-8",
    )
    library_id, collection_name, collection_key, items = load_snapshot(snapshot)
    plan = build_zotero_plan(
        [],
        items,
        library_id=library_id,
        collection_name=collection_name,
        collection_key=collection_key,
    )
    manifest = plan_to_manifest(plan)

    assert manifest["mode"] == "review-only"
    assert [mutation["item_key"] for mutation in manifest["mutations"]] == ["ITEM1"]
    assert manifest["mutations"][0]["remove_tags_review"] == ["GNN"]
    assert manifest["mutations"][0]["metadata_review"]["doi_state"] == "missing"


def test_build_plan_warns_about_stale_bindings(tmp_path):
    wiki_dir = tmp_path / "wiki"
    _write_page(wiki_dir, "Stale-Page", item_key="DEAD0001", title="Stale Paper")

    wiki = WikiManager(wiki_dir)
    bindings = collect_zotero_bindings(wiki)
    # 快照中没有 DEAD0001 —— 绑定悬空
    snapshot_items = [
        SnapshotItem(item_key="LIVE0001", title="Other", item_type="journalArticle")
    ]
    plan = build_zotero_plan(bindings, snapshot_items)
    assert any("zotero-heal" in warning for warning in plan.warnings)
    assert any("DEAD0001" in warning for warning in plan.warnings)
