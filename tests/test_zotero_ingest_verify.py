"""Tests for collection ingest allocation and page verification."""

from __future__ import annotations

from src.llm_wiki.zotero.ingest_verify import (
    ingest_report_to_manifest,
    verify_collection_ingest,
)


def write_snapshot(path, keys=("ITEM0001", "ITEM0002")):
    items = "\n".join(
        f"  - item_key: {key}\n    title: Source {index}\n    item_type: webpage"
        for index, key in enumerate(keys, 1)
    )
    path.write_text(
        f"""version: 1
collection: {{name: blogs/DeepLearning, key: COLL0001}}
items:
{items}
""",
        encoding="utf-8",
    )


def write_ledger(path, rows):
    body = "\n".join(rows)
    path.write_text(
        f"""version: 1
collection:
  key: COLL0001
  snapshot_count: {len(rows)}
allocations:
{body}
""",
        encoding="utf-8",
    )


def write_page(wiki, stem, item_key, *, suffix=""):
    wiki.mkdir(parents=True, exist_ok=True)
    (wiki / f"{stem}.md").write_text(
        f"""---
created: 2026-08-27
updated: 2026-08-27
sources: []
sources_meta:
  - title: Source
    type: webpage
    zotero_item_key: {item_key}
tags: [AI/ML]
status: active
---

# {stem}

{stem} is a reusable technical concept grounded in the allocated source.

## Mechanism

The source-specific mechanism is explained here with enough detail for review.

## Related Pages

- [[Deep-Learning]]

## Sources

- Zotero item {item_key}

## Changelog

- 2026-08-27: Initial ingest.
{suffix}""",
        encoding="utf-8",
    )


def test_valid_collection_ingest_passes_all_required_checks(tmp_path):
    snapshot = tmp_path / "snapshot.yaml"
    ledger = tmp_path / "allocation.yaml"
    wiki = tmp_path / "wiki"
    write_snapshot(snapshot)
    write_ledger(
        ledger,
        [
            "  - item_index: 1\n    item_key: ITEM0001\n    status: ingested\n    pages: [Page-One]",
            "  - item_index: 2\n    item_key: ITEM0002\n    status: ingested\n    pages: [Page-Two]",
        ],
    )
    write_page(wiki, "Page-One", "ITEM0001")
    write_page(wiki, "Page-Two", "ITEM0002")

    report = verify_collection_ingest(wiki, snapshot, ledger)

    assert report.passed is True
    assert report.snapshot_count == 2
    assert report.allocation_count == 2
    assert report.errors == ()


def test_allocation_requires_exact_unique_snapshot_coverage(tmp_path):
    snapshot = tmp_path / "snapshot.yaml"
    ledger = tmp_path / "allocation.yaml"
    wiki = tmp_path / "wiki"
    write_snapshot(snapshot)
    write_ledger(
        ledger,
        [
            "  - item_index: 1\n    item_key: ITEM0001\n    status: ingested\n    pages: [Page-One]",
            "  - item_index: 1\n    item_key: ITEM0001\n    status: omitted\n    omission_reason: duplicate",
        ],
    )
    write_page(wiki, "Page-One", "ITEM0001")

    report = verify_collection_ingest(wiki, snapshot, ledger)
    codes = {issue.code for issue in report.errors}

    assert report.passed is False
    assert "duplicate-item-key" in codes
    assert "duplicate-item-index" in codes
    assert "snapshot-allocation-mismatch" in codes


def test_allocation_ledger_rejects_unknown_fields(tmp_path):
    snapshot = tmp_path / "snapshot.yaml"
    ledger = tmp_path / "allocation.yaml"
    wiki = tmp_path / "wiki"
    write_snapshot(snapshot, keys=("ITEM0001",))
    write_ledger(
        ledger,
        ["  - item_index: 1\n    item_key: ITEM0001\n    status: omitted\n    omission_reason: duplicate\n    metadata: forbidden"],
    )

    report = verify_collection_ingest(wiki, snapshot, ledger)

    assert any(issue.code == "invalid-allocation-ledger" for issue in report.errors)


def test_omission_requires_a_concrete_reason(tmp_path):
    snapshot = tmp_path / "snapshot.yaml"
    ledger = tmp_path / "allocation.yaml"
    wiki = tmp_path / "wiki"
    write_snapshot(snapshot, keys=("ITEM0001",))
    write_ledger(
        ledger,
        ["  - item_index: 1\n    item_key: ITEM0001\n    status: omitted"],
    )

    report = verify_collection_ingest(wiki, snapshot, ledger)

    assert any(issue.code == "missing-omission-reason" for issue in report.errors)


def test_non_omitted_page_requires_matching_sources_meta_binding(tmp_path):
    snapshot = tmp_path / "snapshot.yaml"
    ledger = tmp_path / "allocation.yaml"
    wiki = tmp_path / "wiki"
    write_snapshot(snapshot, keys=("ITEM0001",))
    write_ledger(
        ledger,
        ["  - item_index: 1\n    item_key: ITEM0001\n    status: ingested\n    pages: [Wrong-Binding]"],
    )
    write_page(wiki, "Wrong-Binding", "OTHER001")

    report = verify_collection_ingest(wiki, snapshot, ledger)

    assert any(issue.code == "missing-provenance-binding" for issue in report.errors)


def test_page_hygiene_detects_private_paths_control_chars_and_trailing_space(tmp_path):
    snapshot = tmp_path / "snapshot.yaml"
    ledger = tmp_path / "allocation.yaml"
    wiki = tmp_path / "wiki"
    write_snapshot(snapshot, keys=("ITEM0001",))
    write_ledger(
        ledger,
        ["  - item_index: 1\n    item_key: ITEM0001\n    status: ingested\n    pages: [Unsafe-Page]"],
    )
    write_page(
        wiki,
        "Unsafe-Page",
        "ITEM0001",
        suffix="\nLocal: C:\\Users\\private\\Zotero\\storage\\ABCD1234\\paper.pdf  \nBad:\x07\n",
    )

    report = verify_collection_ingest(wiki, snapshot, ledger)
    codes = {issue.code for issue in report.errors}

    assert {"private-path-leak", "control-character", "trailing-whitespace"} <= codes


def test_template_collapse_is_advisory(tmp_path):
    snapshot = tmp_path / "snapshot.yaml"
    ledger = tmp_path / "allocation.yaml"
    wiki = tmp_path / "wiki"
    keys = ("ITEM0001", "ITEM0002", "ITEM0003")
    write_snapshot(snapshot, keys=keys)
    write_ledger(
        ledger,
        [
            f"  - item_index: {index}\n    item_key: {key}\n    status: ingested\n    pages: [Page-{index}]"
            for index, key in enumerate(keys, 1)
        ],
    )
    for index, key in enumerate(keys, 1):
        write_page(wiki, f"Page-{index}", key)

    report = verify_collection_ingest(wiki, snapshot, ledger)
    manifest = ingest_report_to_manifest(report)

    assert report.passed is True
    assert any(issue.code == "template-collapse" for issue in report.warnings)
    assert manifest["summary"]["warnings"] >= 1
