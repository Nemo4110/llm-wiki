from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from llm_wiki.zotero.cache import EnrichmentCache
from llm_wiki.zotero.mcp_client import ZoteroMCPClient
from llm_wiki.zotero.refresh import (
    DOI_MISSING_TAG,
    PUBLICATION_REVIEW_TAG,
    RefreshItem,
    RefreshSettings,
    RefreshWorker,
    build_refresh_report,
    parse_extra_keys,
    report_to_manifest,
    title_similarity,
)


class FakeCrossref:
    def __init__(self, *, work=None, candidates=None):
        self.work = work or {}
        self.candidates = candidates or []

    async def get_work(self, doi: str):
        return self.work

    async def search_works(self, title: str, *, author: str = "", rows: int = 5):
        return self.candidates


class FakeOpenAlex:
    def __init__(self, *, work=None, source=None):
        self.work = work or {}
        self.source = source or {}

    async def get_work_by_doi(self, doi: str):
        return self.work

    async def get_source(self, source_id: str):
        return self.source


def make_item(**overrides):
    values = {
        "item_key": "ITEM0001",
        "title": "Mining Heterogeneous Information Networks: A Structural Analysis Approach",
        "item_type": "journalArticle",
        "date": "2012",
        "doi": "10.1145/2481244.2481248",
        "arxiv": "",
        "url": "https://doi.org/10.1038/wrong",
        "tags": frozenset({DOI_MISSING_TAG}),
        "creators": ("Sun", "Han"),
        "publication_title": "SIGKDD",
        "issn": "1931-0145",
        "extra": "",
    }
    values.update(overrides)
    return RefreshItem(**values)


def test_mcp_get_items_returns_metadata_in_input_order():
    client = ZoteroMCPClient(Path("ignored"))

    async def fake_get(item_key: str):
        return {"key": item_key}

    client.get_item_metadata = fake_get  # type: ignore[method-assign]
    result = asyncio.run(client.get_items(["ITEM0001", "ITEM0002"], concurrency=2))
    assert result == [{"key": "ITEM0001"}, {"key": "ITEM0002"}]


def test_parse_extra_keys_uses_last_value():
    result = parse_extra_keys(
        "TLDR: hello\nLLM-Wiki DOI Status: missing\nLLM-Wiki DOI Status: verified"
    )
    assert result["TLDR"] == "hello"
    assert result["LLM-Wiki DOI Status"] == "verified"


def test_title_similarity_accepts_subtitle_difference():
    assert (
        title_similarity(
            "Mining Heterogeneous Information Networks: A Structural Analysis Approach",
            "Mining heterogeneous information networks",
        )
        >= 0.94
    )


def test_cache_respects_freshness(tmp_path: Path):
    path = tmp_path / "cache.sqlite"
    now = datetime(2026, 8, 23, tzinfo=UTC)
    with EnrichmentCache(path) as cache:
        cache.put_json("ITEM0001", "crossref", "doi:x", {"ok": True}, checked_at=now)
        assert cache.get_json(
            "ITEM0001", "crossref", "doi:x", max_age_days=30, now=now
        ) == {"ok": True}
        assert (
            cache.get_json(
                "ITEM0001",
                "crossref",
                "doi:x",
                max_age_days=30,
                now=datetime(2026, 9, 23, tzinfo=UTC),
            )
            is None
        )


def test_verified_doi_builds_safe_metric_updates(tmp_path: Path):
    crossref_work = {
        "DOI": "10.1145/2481244.2481248",
        "title": ["Mining heterogeneous information networks"],
        "author": [{"family": "Sun"}],
        "published": {"date-parts": [[2012]]},
        "is-referenced-by-count": 320,
    }
    openalex_work = {
        "id": "https://openalex.org/W2075010670",
        "cited_by_count": 512,
        "primary_location": {"source": {"id": "https://openalex.org/S4210176598"}},
    }
    openalex_source = {"summary_stats": {"2yr_mean_citedness": 10.5, "h_index": 106}}
    with EnrichmentCache(tmp_path / "cache.sqlite") as cache:
        worker = RefreshWorker(
            FakeCrossref(work=crossref_work),
            FakeOpenAlex(work=openalex_work, source=openalex_source),
            cache,
            RefreshSettings(),
            today=date(2026, 8, 23),
            force=True,
        )
        mutation = asyncio.run(worker.refresh_item(make_item()))

    assert mutation.doi_status == "verified"
    assert mutation.citation_count == 512
    assert mutation.safe_set_keys["LLM-Wiki DOI Status"] == "verified"
    assert mutation.safe_set_keys["LLM-Wiki OpenAlex ID"] == "W2075010670"
    assert mutation.safe_set_keys["LLM-Wiki DOI Check Provider"] == "Crossref"
    assert mutation.safe_set_keys["LLM-Wiki Journal 2yr Citedness"] == "10.5"
    assert mutation.safe_set_keys["LLM-Wiki Journal H-Index"] == "106"
    assert mutation.safe_fields["url"] == "https://doi.org/10.1145/2481244.2481248"
    assert mutation.remove_tags == {DOI_MISSING_TAG}
    assert not mutation.metadata_review


def test_existing_doi_accepts_crossref_short_title_when_author_and_year_match(
    tmp_path: Path,
):
    item = make_item(
        title="LightGCN: Simplifying and Powering Graph Convolution Network for Recommendation",
        date="2020",
        doi="10.1145/3397271.3401063",
        creators=("He",),
        tags=frozenset(),
        url="https://dl.acm.org/doi/10.1145/3397271.3401063",
    )
    work = {
        "DOI": item.doi,
        "title": ["LightGCN"],
        "author": [{"family": "He"}],
        "published": {"date-parts": [[2020]]},
    }
    with EnrichmentCache(tmp_path / "cache.sqlite") as cache:
        worker = RefreshWorker(
            FakeCrossref(work=work),
            FakeOpenAlex(),
            cache,
            RefreshSettings(),
            today=date(2026, 8, 23),
            force=True,
        )
        mutation = asyncio.run(worker.refresh_item(item))

    assert mutation.doi_status == "verified"
    assert not mutation.metadata_review


def test_preprint_candidate_requires_review(tmp_path: Path):
    candidate = {
        "DOI": "10.1000/published",
        "title": ["Graph Neural Retrieval for Large Language Model Reasoning"],
        "author": [{"family": "Example"}],
        "published": {"date-parts": [[2025]]},
    }
    item = make_item(
        title="Graph Neural Retrieval for Large Language Model Reasoning",
        item_type="preprint",
        date="2024",
        doi="",
        url="https://arxiv.org/abs/2405.20139",
        arxiv="2405.20139",
        creators=("Example",),
        tags=frozenset(),
    )
    with EnrichmentCache(tmp_path / "cache.sqlite") as cache:
        worker = RefreshWorker(
            FakeCrossref(candidates=[candidate]),
            FakeOpenAlex(),
            cache,
            RefreshSettings(),
            today=date(2026, 8, 23),
            force=True,
        )
        mutation = asyncio.run(worker.refresh_item(item))

    assert mutation.doi_status == "review"
    assert mutation.metadata_review["doi_candidate"]["doi"] == "10.1000/published"
    assert (
        mutation.metadata_review["published_version_candidate"]["doi"]
        == "10.1000/published"
    )
    assert mutation.safe_set_keys["LLM-Wiki Publication Status"] == "candidate-found"
    assert mutation.add_tags == {PUBLICATION_REVIEW_TAG}
    assert "doi" not in mutation.safe_fields


def test_review_candidate_is_reconstructed_from_extra_without_provider_call(
    tmp_path: Path,
):
    item = make_item(
        item_type="preprint",
        doi="",
        extra=(
            "LLM-Wiki DOI Status: review\n"
            "LLM-Wiki DOI Checked: 2026-08-23\n"
            "LLM-Wiki DOI Candidate: 10.1000/published\n"
            "LLM-Wiki Publication Checked: 2026-08-23"
        ),
        tags=frozenset({PUBLICATION_REVIEW_TAG}),
    )
    with EnrichmentCache(tmp_path / "cache.sqlite") as cache:
        worker = RefreshWorker(
            FakeCrossref(),
            FakeOpenAlex(),
            cache,
            RefreshSettings(),
            today=date(2026, 8, 23),
            force=False,
        )
        mutation = asyncio.run(worker.refresh_item(item))

    assert mutation.metadata_review["doi_candidate"]["doi"] == "10.1000/published"
    assert (
        mutation.metadata_review["published_version_candidate"]["source"]
        == "Zotero Extra"
    )
    assert not mutation.has_safe_changes


def test_missing_doi_adds_managed_status_tag(tmp_path: Path):
    item = make_item(doi="", url="", tags=frozenset(), creators=("Unknown",))
    with EnrichmentCache(tmp_path / "cache.sqlite") as cache:
        worker = RefreshWorker(
            FakeCrossref(candidates=[]),
            FakeOpenAlex(),
            cache,
            RefreshSettings(),
            today=date(2026, 8, 23),
            force=True,
        )
        mutation = asyncio.run(worker.refresh_item(item))

    assert mutation.doi_status == "missing"
    assert mutation.add_tags == {DOI_MISSING_TAG}
    assert mutation.safe_set_keys["LLM-Wiki DOI Checked"] == "2026-08-23"


def test_report_manifest_keeps_safe_and_review_sections(tmp_path: Path):
    item = make_item(
        doi="", item_type="preprint", creators=("Example",), tags=frozenset()
    )
    candidate = {
        "DOI": "10.1000/published",
        "title": [item.title],
        "author": [{"family": "Example"}],
        "published": {"date-parts": [[2013]]},
    }
    with EnrichmentCache(tmp_path / "cache.sqlite") as cache:
        worker = RefreshWorker(
            FakeCrossref(candidates=[candidate]),
            FakeOpenAlex(),
            cache,
            RefreshSettings(),
            today=date(2026, 8, 23),
            force=True,
        )
        report = asyncio.run(
            build_refresh_report(
                [item],
                worker,
                collection_key="A9VNJUPI",
                collection_name="GNN",
                concurrency=1,
            )
        )

    manifest = report_to_manifest(report)
    assert manifest["mode"] == "review-only"
    assert manifest["items"][0]["safe_updates"]["add_tags"] == [PUBLICATION_REVIEW_TAG]
    assert "published_version_candidate" in manifest["items"][0]["metadata_review"]


def test_get_items_tolerant_keeps_successes_and_reports_failures():
    from llm_wiki.zotero.mcp_client import ZoteroMCPError

    client = ZoteroMCPClient(Path("ignored"))

    async def fake_get(item_key: str):
        if item_key == "DEAD0001":
            raise ZoteroMCPError("not found")
        return {"key": item_key}

    client.get_item_metadata = fake_get  # type: ignore[method-assign]
    items, failures = asyncio.run(
        client.get_items_tolerant(["ITEM0001", "DEAD0001", "ITEM0002"], concurrency=2)
    )
    assert items == [{"key": "ITEM0001"}, {"key": "ITEM0002"}]
    assert failures == [("DEAD0001", "not found")]


def test_get_items_remains_strict_for_atomic_callers():
    from llm_wiki.zotero.mcp_client import ZoteroMCPError

    client = ZoteroMCPClient(Path("ignored"))

    async def fake_get(item_key: str):
        raise ZoteroMCPError("boom")

    client.get_item_metadata = fake_get  # type: ignore[method-assign]
    with pytest.raises(ZoteroMCPError):
        asyncio.run(client.get_items(["DEAD0001"]))


def test_failed_item_mutations_marks_pending_heal():
    from llm_wiki.zotero.refresh import failed_item_mutations

    mutations = failed_item_mutations([("DEAD0001", "not found")])
    assert len(mutations) == 1
    mutation = mutations[0]
    assert mutation.item_key == "DEAD0001"
    assert mutation.has_safe_changes is False
    assert any("not found" in error for error in mutation.errors)
