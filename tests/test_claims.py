"""
Tests for claims.py - claim-level provenance validation
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


from llm_wiki.claims import validate_claims
from llm_wiki.core import WikiManager


def _page_with(tmp_path, claims, sources=None, status="active"):
    """创建一个带 claims 的页面,返回 (wiki, page)"""
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir(exist_ok=True)
    wiki = WikiManager(wiki_dir)
    fm = {
        "created": "2026-08-01",
        "updated": "2026-08-01",
        "tags": ["test"],
        "status": status,
        "sources": sources or [],
        "claims": claims,
    }
    wiki.create_page("ClaimPage", "# ClaimPage\n\n正文。\n", fm)
    return wiki, wiki.get_page("ClaimPage")


class TestClaimSchema:
    def test_valid_claims_pass(self, tmp_path):
        _wiki, page = _page_with(
            tmp_path,
            claims=[
                {
                    "text": "LoRA 用低秩分解",
                    "source": "sources/lora.pdf",
                    "status": "accepted",
                }
            ],
            sources=["sources/lora.pdf"],
        )
        assert validate_claims(page, tmp_path) == []

    def test_claim_must_cite_declared_source(self, tmp_path):
        _wiki, page = _page_with(
            tmp_path,
            claims=[
                {"text": "X 结论", "source": "sources/other.pdf", "status": "accepted"}
            ],
            sources=["sources/lora.pdf"],
        )
        issues = validate_claims(page, tmp_path)
        assert any("undeclared" in i and "sources/other.pdf" in i for i in issues)

    def test_claim_status_vocabulary(self, tmp_path):
        _wiki, page = _page_with(
            tmp_path,
            claims=[{"text": "X", "source": "sources/lora.pdf", "status": "proven"}],
            sources=["sources/lora.pdf"],
        )
        issues = validate_claims(page, tmp_path)
        assert any("proven" in i and "status" in i for i in issues)

    def test_claim_missing_fields(self, tmp_path):
        _wiki, page = _page_with(
            tmp_path,
            claims=[{"text": "只有文本"}],
        )
        issues = validate_claims(page, tmp_path)
        assert any("missing" in i for i in issues)

    def test_source_alias_from_sources_meta_accepted(self, tmp_path):
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir(exist_ok=True)
        wiki = WikiManager(wiki_dir)
        fm = {
            "created": "2026-08-01",
            "updated": "2026-08-01",
            "status": "active",
            "sources": ["sources/zotero/paper.md"],
            "sources_meta": [
                {"title": "Paper", "source_alias": "sources/zotero/paper.md"}
            ],
            "claims": [
                {
                    "text": "X",
                    "source": "sources/zotero/paper.md",
                    "status": "provisional",
                }
            ],
        }
        wiki.create_page("P2", "# P2\n\n正文。\n", fm)
        page = wiki.get_page("P2")
        assert validate_claims(page, tmp_path) == []


class TestMaturityClaims:
    def test_mature_page_with_unsettled_claims_flagged(self, tmp_path):
        _wiki, page = _page_with(
            tmp_path,
            claims=[
                {"text": "未定论", "source": "sources/lora.pdf", "status": "contested"}
            ],
            sources=["sources/lora.pdf"],
            status="mature",
        )
        issues = validate_claims(page, tmp_path)
        assert any("contested" in i and "mature" in i for i in issues)

    def test_developing_page_with_unsettled_claims_ok(self, tmp_path):
        _wiki, page = _page_with(
            tmp_path,
            claims=[
                {"text": "未定论", "source": "sources/lora.pdf", "status": "contested"}
            ],
            sources=["sources/lora.pdf"],
            status="developing",
        )
        assert validate_claims(page, tmp_path) == []

    def test_page_without_claims_passes(self, tmp_path):
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir(exist_ok=True)
        wiki = WikiManager(wiki_dir)
        wiki.create_page("Plain", "# Plain\n\n正文。\n", {"status": "active"})
        assert validate_claims(wiki.get_page("Plain"), tmp_path) == []


class TestLintIntegration:
    def test_lint_reports_claim_issues(self, tmp_path):
        _page_with(
            tmp_path,
            claims=[{"text": "X", "source": "sources/other.pdf", "status": "accepted"}],
            sources=["sources/lora.pdf"],
        )
        wiki = WikiManager(tmp_path / "wiki")
        issues = wiki.lint()
        assert "claim_issues" in issues
        assert any("ClaimPage" in i for i in issues["claim_issues"])
