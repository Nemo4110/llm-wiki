"""
Tests for scripts/agent-bridge.py — all 8 subcommands.

Run individually:
    pytest tests/test_agent_bridge.py -v

Note: agent-bridge.py is imported dynamically (filename contains a hyphen).
"""

import argparse
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest


# Helper to build argparse.Namespace for each subcommand
def _args(**kwargs):
    return argparse.Namespace(**kwargs)


class TestCmdCheck:
    def test_find_python_disables_bytecode_for_probe(
        self, agent_bridge_module, monkeypatch, tmp_path
    ):
        calls = []

        class Result:
            returncode = 0

        def fake_run(command, **kwargs):
            calls.append((command, kwargs))
            return Result()

        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", tmp_path)
        monkeypatch.setattr(agent_bridge_module.subprocess, "run", fake_run)

        python_path, is_venv = agent_bridge_module._find_python()

        assert python_path == sys.executable
        assert is_venv is False
        # The probe must run the current interpreter with bytecode writes disabled.
        command = calls[0][0]
        assert command[0] == sys.executable
        assert "-B" in command
        assert "-c" in command

    def test_ready_when_wiki_exists(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.cmd_check(_args())
        out = capsys.readouterr().out
        assert rc == 0
        assert "[READY]" in out
        assert "Transformer" in out

    def test_not_ready_without_wiki(
        self, agent_bridge_module, monkeypatch, capsys, tmp_path
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", tmp_path)
        rc = agent_bridge_module.cmd_check(_args())
        out = capsys.readouterr().out
        assert rc == 1
        # Library may still be importable (PARTIAL) or not (NOT READY) depending on path
        assert "[PARTIAL]" in out or "[NOT READY]" in out


class TestCmdLink:
    def test_link_found(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        args = _args(source="Transformer", mode="light", max_related=5)
        rc = agent_bridge_module.cmd_link(args)
        out = capsys.readouterr().out
        assert rc == 0
        assert "Relation Discovery" in out
        # LoRA shares tags and links to Transformer, so it should appear
        assert "LoRA" in out

    def test_link_not_found(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        args = _args(source="NonExistent", mode="light", max_related=5)
        rc = agent_bridge_module.cmd_link(args)
        out = capsys.readouterr().out
        assert rc == 1
        assert "not found" in out.lower()

    def test_link_no_relations(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        # Create an isolated page with no shared tags/keywords/links
        from llm_wiki.core import WikiManager

        wiki = WikiManager(temp_wiki_root / "wiki")
        wiki.create_page(
            "Isolated",
            "# Isolated\n\nUnique content with no overlap.",
            {"created": "2026-04-01", "status": "active"},
        )
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        args = _args(source="Isolated", mode="light", max_related=5)
        rc = agent_bridge_module.cmd_link(args)
        out = capsys.readouterr().out
        assert rc == 0
        assert "No significant relations" in out


class TestCmdRelink:
    def test_relink_finds_new_pages(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        args = _args(since=today, mode="light", dry_run=True)
        rc = agent_bridge_module.cmd_relink(args)
        out = capsys.readouterr().out
        assert rc == 0
        assert "Global Relink Report" in out

    def test_relink_invalid_date(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        args = _args(since="not-a-date", mode="light", dry_run=True)
        rc = agent_bridge_module.cmd_relink(args)
        out = capsys.readouterr().out
        assert rc == 1
        assert "Invalid date" in out

    def test_relink_no_new_pages(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        future = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%d")
        args = _args(since=future, mode="light", dry_run=True)
        rc = agent_bridge_module.cmd_relink(args)
        out = capsys.readouterr().out
        assert rc == 0
        assert "No new pages" in out


class TestCmdLint:
    def test_lint_reports_issues(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.cmd_lint(_args())
        out = capsys.readouterr().out
        assert rc == 0  # lint always returns 0 even if issues found
        assert "Wiki Health Check" in out

    def test_lint_reports_shallow_pages_with_reasons(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        from llm_wiki.core import WikiManager

        source_dir = temp_wiki_root / "sources"
        source_dir.mkdir()
        (source_dir / "large.md").write_text("x" * 12_000, encoding="utf-8")

        wiki = WikiManager(temp_wiki_root / "wiki")
        wiki.create_page(
            "Thin",
            "# Thin\n\nOnly a tiny summary.",
            {
                "created": "2026-07-25",
                "status": "active",
                "sources": ["sources/large.md"],
            },
        )
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)

        rc = agent_bridge_module.cmd_lint(_args())
        out = capsys.readouterr().out

        assert agent_bridge_module._md_table_cell("A|B\nC") == r"A\|B C"
        assert rc == 0
        assert "Shallow pages" in out
        assert "### Shallow Pages (advisory)" in out
        assert (
            "| Page | Knowledge | Paragraphs | Sections | Sources | "
            "Source chars | Compression | Reasons |"
        ) in out
        assert "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |" in out
        assert "[Thin](wiki/Thin.md)" in out
        assert "`short-knowledge-body`" in out
        assert "12,000" in out
        assert re.search(r"\d+\.\d{2}%", out)

        shallow_section = out.split("### Shallow Pages (advisory)", 1)[1].split(
            "> **[ACTION]**", 1
        )[0]
        assert "```" not in shallow_section

    def test_lint_no_wiki(self, agent_bridge_module, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", tmp_path)
        rc = agent_bridge_module.cmd_lint(_args())
        out = capsys.readouterr().out
        assert rc == 1
        assert "Cannot find wiki" in out


class TestCmdStatus:
    def test_status_shows_overview(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.cmd_status(_args())
        out = capsys.readouterr().out
        assert rc == 0
        assert "Wiki Status" in out
        assert "Transformer" in out or "Total Pages" in out

    def test_status_no_wiki(self, agent_bridge_module, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", tmp_path)
        rc = agent_bridge_module.cmd_status(_args())
        capsys.readouterr()
        assert rc == 1


class TestCmdMerge:
    def test_merge_dry_run(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        from llm_wiki.core import WikiManager

        wiki = WikiManager(temp_wiki_root / "wiki")
        wiki.create_page(
            "SourcePage",
            "# SourcePage\n\nSource content.",
            {"created": "2026-04-01", "status": "active"},
        )
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        args = _args(
            source="SourcePage",
            target="Transformer",
            strategy="link_only",
            dry_run=True,
        )
        rc = agent_bridge_module.cmd_merge(args)
        out = capsys.readouterr().out
        assert rc == 0
        assert "dry-run" in out.lower() or "Dry-run" in out
        # File should NOT be modified
        page = wiki.get_page("Transformer")
        assert "SourcePage" not in page.content

    def test_merge_apply_uses_transaction_journal(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        from llm_wiki.core import WikiManager

        wiki = WikiManager(temp_wiki_root / "wiki")
        wiki.create_page(
            "SourcePage",
            "# SourcePage\n\nSource content.",
            {"created": "2026-04-01", "status": "active"},
        )
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        args = _args(
            source="SourcePage",
            target="Transformer",
            strategy="append_related",
            dry_run=False,
        )

        rc = agent_bridge_module.cmd_merge(args)
        out = capsys.readouterr().out

        assert rc == 0
        assert "Transaction:" in out
        assert "SourcePage" in wiki.get_page("Transformer").content
        journals = list((temp_wiki_root / ".backups" / "transactions").iterdir())
        assert len(journals) == 1

    def test_merge_source_not_found(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        args = _args(
            source="Missing", target="Transformer", strategy="link_only", dry_run=True
        )
        rc = agent_bridge_module.cmd_merge(args)
        out = capsys.readouterr().out
        assert rc == 1
        assert "not found" in out.lower()

    def test_merge_target_not_found(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        args = _args(
            source="Transformer", target="Missing", strategy="link_only", dry_run=True
        )
        rc = agent_bridge_module.cmd_merge(args)
        capsys.readouterr()
        assert rc == 1

    def test_merge_strategy_not_allowed(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        # Update config to remove update_concept from allowed strategies
        config_text = (temp_wiki_root / "config.yaml").read_text(encoding="utf-8")
        config_text = config_text.replace("      - update_concept\n", "")
        (temp_wiki_root / "config.yaml").write_text(config_text, encoding="utf-8")

        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        args = _args(
            source="Transformer", target="LoRA", strategy="update_concept", dry_run=True
        )
        rc = agent_bridge_module.cmd_merge(args)
        out = capsys.readouterr().out
        assert rc == 1
        assert "not allowed" in out.lower()


class TestCmdQuery:
    def test_query_fallback_when_embedding_disabled(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        args = _args(query_text="What is LoRA?", semantic=False)
        rc = agent_bridge_module.cmd_query(args)
        out = capsys.readouterr().out
        assert rc == 0
        assert "Falling back" in out or "LoRA" in out

    def test_query_no_wiki(self, agent_bridge_module, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", tmp_path)
        args = _args(query_text="test", semantic=False)
        rc = agent_bridge_module.cmd_query(args)
        capsys.readouterr()
        assert rc == 1


class TestCmdIndex:
    def test_index_disabled(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        args = _args(force=False)
        rc = agent_bridge_module.cmd_index(args)
        out = capsys.readouterr().out
        # embedding is disabled by default in config, so should error
        assert rc == 1
        assert "disabled" in out.lower()

    def test_index_no_wiki(self, agent_bridge_module, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", tmp_path)
        args = _args(force=False)
        rc = agent_bridge_module.cmd_index(args)
        capsys.readouterr()
        assert rc == 1


class TestMain:
    def test_main_dispatch_check(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.main(["check"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "Environment Check" in out

    def test_main_help(self, agent_bridge_module, capsys):
        # --help triggers SystemExit(0) from argparse; wrap in pytest.raises
        with pytest.raises(SystemExit) as exc_info:
            agent_bridge_module.main(["--help"])
        assert exc_info.value.code == 0

    def test_main_link_with_args(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.main(
            ["link", "--source", "Transformer", "--mode", "light"]
        )
        out = capsys.readouterr().out
        assert rc == 0
        assert "Relation Discovery" in out


class TestCmdZoteroPlan:
    def test_zotero_plan_snapshot_is_read_only(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        page = temp_wiki_root / "wiki" / "Graph-Neural-Networks.md"
        page.write_text(
            """---
created: 2026-08-23
updated: 2026-08-23
sources: []
source_types:
  - academic_paper
sources_meta:
  - title: Graph Paper
    type: academic_paper
    zotero_item_key: ITEM0001
    library_id: "0"
coverage_verified: true
tags:
  - AI/ML
status: active
---

# Graph Neural Networks

Knowledge body.
""",
            encoding="utf-8",
        )
        snapshot = temp_wiki_root / "gnn.yaml"
        snapshot.write_text(
            """version: 1
library_id: "0"
collection:
  name: GNN
  key: A9VNJUPI
items:
  - item_key: ITEM0001
    title: Graph Paper
    item_type: conferencePaper
    doi: ""
    tags: [GNN]
""",
            encoding="utf-8",
        )
        original = snapshot.read_text(encoding="utf-8")

        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.main(["zotero-plan", "--snapshot", "gnn.yaml"])
        out = capsys.readouterr().out

        assert rc == 0
        assert "Zotero Sync Plan: GNN" in out
        assert "llm-wiki:AI/ML" in out
        assert "llm-wiki:ingested" in out
        assert "GNN" in out
        assert "Read-only plan" in out
        assert snapshot.read_text(encoding="utf-8") == original

        rc = agent_bridge_module.main(
            [
                "zotero-plan",
                "--snapshot",
                "gnn.yaml",
                "--manifest-out",
                "temp/gnn-manifest.yaml",
            ]
        )
        assert rc == 0
        manifest = temp_wiki_root / "temp" / "gnn-manifest.yaml"
        assert manifest.exists()
        manifest_text = manifest.read_text(encoding="utf-8")
        assert "mode: review-only" in manifest_text
        assert "remove_tags_review" in manifest_text

    def test_zotero_plan_missing_snapshot(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.main(["zotero-plan", "--snapshot", "missing.yaml"])
        out = capsys.readouterr().out

        assert rc == 1
        assert "Snapshot not found" in out

    def test_zotero_plan_rejects_manifest_outside_temp(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        snapshot = temp_wiki_root / "gnn.yaml"
        snapshot.write_text(
            """version: 1
collection: {name: GNN, key: A9VNJUPI}
items:
  - item_key: ITEMX
    title: Example
    item_type: conferencePaper
    doi: ""
    tags: []
""",
            encoding="utf-8",
        )
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.main(
            [
                "zotero-plan",
                "--snapshot",
                "gnn.yaml",
                "--manifest-out",
                "outside.yaml",
            ]
        )
        out = capsys.readouterr().out

        assert rc == 1
        assert "must stay under" in out

    def test_zotero_plan_removal_plan_out_scoped_to_retired_bindings(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        page = temp_wiki_root / "wiki" / "Graph-Neural-Networks.md"
        page.write_text(
            """---
created: 2026-08-23
updated: 2026-08-23
sources: []
source_types:
  - academic_paper
sources_meta:
  - title: Graph Paper
    type: academic_paper
    zotero_item_key: ITEM0001
    library_id: "0"
coverage_verified: true
tags:
  - AI/ML
status: active
---

# Graph Neural Networks

Knowledge body.
""",
            encoding="utf-8",
        )
        snapshot = temp_wiki_root / "gnn.yaml"
        snapshot.write_text(
            """version: 1
library_id: "0"
collection:
  name: GNN
  key: A9VNJUPI
items:
  - item_key: ITEM0001
    title: Graph Paper
    item_type: conferencePaper
    doi: ""
    tags: [llm-wiki:Graph-Neural-Networks, llm-wiki:AI/ML, manual-note]
""",
            encoding="utf-8",
        )
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.main(
            [
                "zotero-plan",
                "--snapshot",
                "gnn.yaml",
                "--removal-plan-out",
                "temp/gnn-removal.yaml",
            ]
        )
        out = capsys.readouterr().out

        assert rc == 0
        assert "Retired-binding removal plan written to" in out
        removal = temp_wiki_root / "temp" / "gnn-removal.yaml"
        assert removal.exists()
        text = removal.read_text(encoding="utf-8")
        assert "mode: authorized-write" in text
        assert "allow_managed_removals: true" in text
        # Only the retired page-stem binding tag is whitelisted for removal;
        # the live topic tag and the unmanaged tag are excluded.
        assert "llm-wiki:Graph-Neural-Networks" in text
        assert "reviewed_removals" in text
        removals_section = text.split("reviewed_removals:", 1)[1]
        assert "llm-wiki:AI/ML" not in removals_section
        assert "manual-note" not in removals_section

    def test_zotero_plan_removal_plan_out_rejects_path_outside_temp(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        snapshot = temp_wiki_root / "gnn.yaml"
        snapshot.write_text(
            """version: 1
collection: {name: GNN, key: A9VNJUPI}
items:
  - item_key: ITEMX
    title: Example
    item_type: conferencePaper
    doi: ""
    tags: []
""",
            encoding="utf-8",
        )
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.main(
            [
                "zotero-plan",
                "--snapshot",
                "gnn.yaml",
                "--removal-plan-out",
                "outside.yaml",
            ]
        )
        out = capsys.readouterr().out

        assert rc == 1
        assert "must stay under" in out


class TestCmdZoteroRefresh:
    def test_refresh_dry_run_writes_review_manifest_under_temp(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        import llm_wiki.zotero.refresh as refresh_module
        from llm_wiki.zotero.refresh import RefreshMutation, RefreshReport

        (temp_wiki_root / ".mcp.json").write_text(
            '{"mcpServers":{"zotero":{"command":"ignored"}}}',
            encoding="utf-8",
        )

        async def fake_run(*args, **kwargs):
            return RefreshReport(
                collection_key="A9VNJUPI",
                collection_name="GNN",
                items=[
                    RefreshMutation(
                        item_key="ITEM0001",
                        title="Graph Paper",
                        doi_status="verified",
                        citation_provider="OpenAlex",
                        citation_count=12,
                        safe_set_keys={"LLM-Wiki Citations OpenAlex": "12"},
                    )
                ],
            )

        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        monkeypatch.setattr(refresh_module, "run_live_refresh", fake_run)
        rc = agent_bridge_module.main(
            [
                "zotero-refresh",
                "--collection-key",
                "A9VNJUPI",
                "--manifest-out",
                "temp/refresh.yaml",
            ]
        )
        out = capsys.readouterr().out

        assert rc == 0
        assert "Zotero Refresh: GNN" in out
        assert "Dry-run only" in out
        assert (temp_wiki_root / "temp" / "refresh.yaml").exists()

    def test_refresh_rejects_cache_outside_var(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        (temp_wiki_root / ".mcp.json").write_text(
            '{"mcpServers":{"zotero":{"command":"ignored"}}}',
            encoding="utf-8",
        )
        (temp_wiki_root / "config.yaml").write_text(
            "zotero_enrichment:\n  cache_path: outside.sqlite\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.main(
            [
                "zotero-refresh",
                "--collection-key",
                "A9VNJUPI",
            ]
        )
        out = capsys.readouterr().out

        assert rc == 1
        assert "must stay under" in out

    def test_refresh_rejects_manifest_outside_temp(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        import llm_wiki.zotero.refresh as refresh_module
        from llm_wiki.zotero.refresh import RefreshReport

        (temp_wiki_root / ".mcp.json").write_text(
            '{"mcpServers":{"zotero":{"command":"ignored"}}}',
            encoding="utf-8",
        )

        async def fake_run(*args, **kwargs):
            return RefreshReport(
                collection_key="A9VNJUPI",
                collection_name="GNN",
                items=[],
            )

        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        monkeypatch.setattr(refresh_module, "run_live_refresh", fake_run)
        rc = agent_bridge_module.main(
            [
                "zotero-refresh",
                "--collection-key",
                "A9VNJUPI",
                "--manifest-out",
                "outside.yaml",
            ]
        )
        out = capsys.readouterr().out

        assert rc == 1
        assert "must stay under" in out


class TestCmdZoteroLocalAuth:
    def test_local_auth_stores_key_under_var(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        import llm_wiki.zotero.local as zl

        captured = {}

        async def fake_authorize(app_name, store_path, **kwargs):
            captured["app_name"] = app_name
            captured["store_path"] = store_path
            return "KEY"

        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        monkeypatch.setattr(zl, "authorize_local", fake_authorize)
        rc = agent_bridge_module.main(["zotero-local-auth"])
        out = capsys.readouterr().out

        assert rc == 0
        assert captured["app_name"] == "llm-wiki"
        assert str(captured["store_path"]).startswith(str(temp_wiki_root / "var"))
        assert "local" in out.lower()


class TestCmdApplyBundle:
    """apply-bundle 子命令:事务化多文件写入"""

    def _make_bundle(self, root: Path, update_hash: str) -> Path:
        import hashlib

        temp = root / "temp"
        temp.mkdir(exist_ok=True)
        (temp / "draft-page.md").write_text(
            "---\ntags: []\n---\n\n# NewPage\n\nbody\n", encoding="utf-8"
        )
        (temp / "draft-index.md").write_text(
            "# Wiki Index\n\n- [[NewPage]]\n", encoding="utf-8"
        )
        (temp / "draft-log.md").write_text(
            "# Log\n\n## [2026-08-24] ingest | NewPage\n", encoding="utf-8"
        )
        manifest = temp / "tx-bundle.yaml"
        manifest.write_text(
            f"""
ops:
  - op: create
    path: wiki/NewPage.md
    content_path: draft-page.md
  - op: update
    path: wiki/index.md
    content_path: draft-index.md
    expected_sha256: "{update_hash}"
  - op: update
    path: log.md
    content_path: draft-log.md
    expected_sha256: "{hashlib.sha256(b"# Log\n").hexdigest()}"
""",
            encoding="utf-8",
        )
        (root / "log.md").write_text("# Log\n", encoding="utf-8")
        return manifest

    def _index_hash(self, root: Path) -> str:
        import hashlib

        content = (root / "wiki" / "index.md").read_text(encoding="utf-8")
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def test_dry_run_previews_without_writing(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        manifest = self._make_bundle(temp_wiki_root, self._index_hash(temp_wiki_root))

        rc = agent_bridge_module.cmd_apply_bundle(
            _args(manifest=str(manifest), dry_run=True)
        )
        out = capsys.readouterr().out

        assert rc == 0
        assert "Transaction Preview" in out
        assert "wiki/NewPage.md" in out
        assert not (temp_wiki_root / "wiki" / "NewPage.md").exists()
        assert (temp_wiki_root / "log.md").read_text(encoding="utf-8") == "# Log\n"

    def test_dry_run_reports_current_hash_when_missing(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        manifest = self._make_bundle(temp_wiki_root, self._index_hash(temp_wiki_root))
        # 去掉 update 的 expected_sha256,模拟 Agent 先探测哈希
        text = manifest.read_text(encoding="utf-8")
        text = "\n".join(l for l in text.split("\n") if "expected_sha256" not in l)
        manifest.write_text(text, encoding="utf-8")

        rc = agent_bridge_module.cmd_apply_bundle(
            _args(manifest=str(manifest), dry_run=True)
        )
        out = capsys.readouterr().out

        assert rc == 0
        assert "current sha256" in out
        assert self._index_hash(temp_wiki_root) in out

    def test_apply_writes_all_files(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        manifest = self._make_bundle(temp_wiki_root, self._index_hash(temp_wiki_root))

        rc = agent_bridge_module.cmd_apply_bundle(
            _args(manifest=str(manifest), dry_run=False)
        )
        out = capsys.readouterr().out

        assert rc == 0
        assert "Applied" in out
        assert (temp_wiki_root / "wiki" / "NewPage.md").exists()
        assert "[[NewPage]]" in (temp_wiki_root / "wiki" / "index.md").read_text(
            encoding="utf-8"
        )
        assert "ingest | NewPage" in (temp_wiki_root / "log.md").read_text(
            encoding="utf-8"
        )

    def test_apply_with_stale_hash_writes_nothing(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        manifest = self._make_bundle(temp_wiki_root, "0" * 64)

        rc = agent_bridge_module.cmd_apply_bundle(
            _args(manifest=str(manifest), dry_run=False)
        )
        out = capsys.readouterr().out

        assert rc == 1
        assert "Hash mismatch" in out or "hash mismatch" in out
        assert not (temp_wiki_root / "wiki" / "NewPage.md").exists()
        assert (temp_wiki_root / "log.md").read_text(encoding="utf-8") == "# Log\n"

    def test_missing_manifest_returns_error(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)

        rc = agent_bridge_module.cmd_apply_bundle(
            _args(manifest=str(temp_wiki_root / "nope.yaml"), dry_run=False)
        )
        out = capsys.readouterr().out

        assert rc == 1
        assert "Error" in out


class TestCmdCapabilities:
    """capabilities 子命令:打印有效契约表"""

    def test_prints_contract_table(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)

        rc = agent_bridge_module.cmd_capabilities(_args())
        out = capsys.readouterr().out

        assert rc == 0
        assert "Capability Contracts" in out
        for command in ("apply-bundle", "lint", "zotero-refresh"):
            assert command in out
        assert "wiki/" in out

    def test_shows_disabled_state_from_config(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        config_path = temp_wiki_root / "config.yaml"
        config_path.write_text(
            config_path.read_text(encoding="utf-8")
            + "\ncapabilities:\n  merge:\n    enabled: false\n",
            encoding="utf-8",
        )

        rc = agent_bridge_module.cmd_capabilities(_args())
        out = capsys.readouterr().out

        assert rc == 0
        assert "disabled" in out

    def test_disabled_command_blocked_at_dispatch(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        config_path = temp_wiki_root / "config.yaml"
        config_path.write_text(
            config_path.read_text(encoding="utf-8")
            + "\ncapabilities:\n  apply-bundle:\n    enabled: false\n",
            encoding="utf-8",
        )

        rc = agent_bridge_module.main(["apply-bundle", "whatever.yaml"])
        out = capsys.readouterr().out

        assert rc == 1
        assert "disabled" in out

    def test_apply_bundle_rejects_out_of_scope_paths(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        temp = temp_wiki_root / "temp"
        temp.mkdir(exist_ok=True)
        (temp / "draft.md").write_text("polluted", encoding="utf-8")
        manifest = temp / "bundle.yaml"
        manifest.write_text(
            """
ops:
  - op: create
    path: sources/generated.md
    content_path: draft.md
""",
            encoding="utf-8",
        )

        rc = agent_bridge_module.cmd_apply_bundle(
            _args(manifest=str(manifest), dry_run=False)
        )
        out = capsys.readouterr().out

        assert rc == 1
        assert "write_scope" in out
        assert not (temp_wiki_root / "sources" / "generated.md").exists()


class TestLifecycleOutput:
    """lint/status 命令暴露生命周期信号"""

    def test_lint_reports_lifecycle_mismatch(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        wiki_dir = temp_wiki_root / "wiki"
        (wiki_dir / "Thin.md").write_text(
            '---\ncreated: "2026-08-01"\nupdated: "2026-08-01"\ntags: ["zz-niche"]\nstatus: "mature"\n---\n\n# Thin\n\n一句话。\n',
            encoding="utf-8",
        )

        rc = agent_bridge_module.cmd_lint(_args())
        out = capsys.readouterr().out

        assert rc == 0
        assert "Lifecycle Mismatch" in out
        assert "Thin" in out

    def test_lint_reports_invalid_status(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        wiki_dir = temp_wiki_root / "wiki"
        (wiki_dir / "Weird.md").write_text(
            '---\ncreated: "2026-08-01"\nupdated: "2026-08-01"\ntags: ["zz-niche"]\nstatus: "publised"\n---\n\n# Weird\n\n内容。\n',
            encoding="utf-8",
        )

        rc = agent_bridge_module.cmd_lint(_args())
        out = capsys.readouterr().out

        assert rc == 0
        assert "Invalid Status" in out
        assert "publised" in out

    def test_status_shows_lifecycle_distribution(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        wiki_dir = temp_wiki_root / "wiki"
        (wiki_dir / "MatureOne.md").write_text(
            '---\ncreated: "2026-08-01"\nupdated: "2026-08-01"\ntags: []\nstatus: "mature"\n---\n\n# MatureOne\n\n内容。\n',
            encoding="utf-8",
        )

        rc = agent_bridge_module.cmd_status(_args())
        out = capsys.readouterr().out

        assert rc == 0
        assert "Lifecycle" in out
        assert "mature" in out


class TestCmdHot:
    """hot 子命令:打印有界最近上下文;apply-bundle 自动维护"""

    def test_apply_bundle_records_hot_entry(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        temp = temp_wiki_root / "temp"
        temp.mkdir(exist_ok=True)
        (temp / "draft.md").write_text("# HotPage\n\nbody\n", encoding="utf-8")
        manifest = temp / "bundle.yaml"
        manifest.write_text(
            """
ops:
  - op: create
    path: wiki/HotPage.md
    content_path: draft.md
""",
            encoding="utf-8",
        )

        rc = agent_bridge_module.cmd_apply_bundle(
            _args(manifest=str(manifest), dry_run=False)
        )
        assert rc == 0
        capsys.readouterr()

        hot = temp_wiki_root / "wiki" / "hot.md"
        assert hot.exists()
        text = hot.read_text(encoding="utf-8")
        assert "wiki/HotPage.md" in text

    def test_hot_prints_recent_context(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        (temp_wiki_root / "wiki" / "hot.md").write_text(
            "# Hot Context\n\n- [2026-08-24 18:00] ingest | X — wiki/X.md\n",
            encoding="utf-8",
        )

        rc = agent_bridge_module.cmd_hot(_args())
        out = capsys.readouterr().out

        assert rc == 0
        assert "ingest | X" in out

    def test_hot_without_file_friendly_message(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)

        rc = agent_bridge_module.cmd_hot(_args())
        out = capsys.readouterr().out

        assert rc == 0
        assert "no recorded activity" in out.lower() or "hot.md" in out


class TestClaimLintOutput:
    def test_lint_reports_claim_issues(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        wiki_dir = temp_wiki_root / "wiki"
        (wiki_dir / "Claimy.md").write_text(
            '---\ncreated: "2026-08-01"\nupdated: "2026-08-01"\ntags: ["zz-niche"]\nstatus: "active"\n'
            'sources:\n  - "sources/lora.pdf"\n'
            'claims:\n  - text: "X 结论"\n    source: "sources/undeclared.pdf"\n    status: "accepted"\n'
            "---\n\n# Claimy\n\n内容。\n",
            encoding="utf-8",
        )

        rc = agent_bridge_module.cmd_lint(_args())
        out = capsys.readouterr().out

        assert rc == 0
        assert "Claim Issues" in out
        assert "undeclared" in out


class TestCmdZoteroCollectionWorkflow:
    def test_writeback_command_is_registered_and_rejects_missing_plan(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)

        rc = agent_bridge_module.main(
            [
                "zotero-writeback",
                "--plan",
                "temp/missing.yaml",
                "--action",
                "audit",
                "--report-out",
                "temp/report.yaml",
            ]
        )
        out = capsys.readouterr().out

        assert rc == 1
        assert "Write plan not found" in out

    def test_ingest_verify_command_writes_report_under_temp(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        temp = temp_wiki_root / "temp"
        temp.mkdir(exist_ok=True)
        snapshot = temp / "snapshot.yaml"
        snapshot.write_text(
            """version: 1
collection: {name: blogs/DeepLearning, key: COLL0001}
items:
  - item_key: ITEM0001
    title: Source
    item_type: webpage
""",
            encoding="utf-8",
        )
        allocation = temp / "allocation.yaml"
        allocation.write_text(
            """version: 1
collection: {key: COLL0001, snapshot_count: 1}
allocations:
  - item_index: 1
    item_key: ITEM0001
    status: ingested
    pages: [Deep-Learning-Source]
""",
            encoding="utf-8",
        )
        page = temp_wiki_root / "wiki" / "Deep-Learning-Source.md"
        page.write_text(
            """---
created: 2026-08-27
updated: 2026-08-27
sources: []
sources_meta:
  - title: Source
    type: webpage
    zotero_item_key: ITEM0001
tags: [AI/ML]
status: active
---

# Deep Learning Source

This page defines a source-specific deep learning concept for durable reuse.

## Mechanism

The source-specific mechanism is described with enough detail for verification.

## Related Pages

- [[Deep-Learning]]

## Sources

- Zotero item ITEM0001

## Changelog

- 2026-08-27: Initial ingest.
""",
            encoding="utf-8",
        )
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)

        rc = agent_bridge_module.main(
            [
                "zotero-ingest-verify",
                "--snapshot",
                "temp/snapshot.yaml",
                "--allocation",
                "temp/allocation.yaml",
                "--report-out",
                "temp/ingest-report.yaml",
            ]
        )
        out = capsys.readouterr().out

        assert rc == 0
        assert "Passed" in out
        report = temp / "ingest-report.yaml"
        assert report.exists()
        assert "passed: true" in report.read_text(encoding="utf-8")


class TestCmdZoteroHeal:
    def _setup_stale_binding(self, temp_wiki_root):
        page = temp_wiki_root / "wiki" / "Deep-Learning-Paper.md"
        page.write_text(
            """---
created: 2026-08-01
updated: 2026-08-01
sources_meta:
  - title: Deep Learning Paper
    type: academic_paper
    doi: 10.1000/xyz
    zotero_item_key: DEAD0001
tags: []
status: active
---

# Deep Learning Paper

Knowledge body.
""",
            encoding="utf-8",
        )
        snapshot = temp_wiki_root / "snap.yaml"
        snapshot.write_text(
            """version: 1
library_id: "0"
collection:
  name: GNN
  key: A9VNJUPI
items:
  - item_key: NEWKEY01
    title: Deep Learning Paper (reprinted)
    item_type: journalArticle
    doi: 10.1000/xyz
    tags: []
""",
            encoding="utf-8",
        )
        return page

    def test_heal_dry_run_reports_stale_without_mutation(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        page = self._setup_stale_binding(temp_wiki_root)
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.main(
            [
                "zotero-heal",
                "--snapshot",
                "snap.yaml",
                "--manifest-out",
                "temp/heal.yaml",
            ]
        )
        out = capsys.readouterr().out

        assert rc == 0
        assert "DEAD0001" in out
        assert "NEWKEY01" in out
        manifest = temp_wiki_root / "temp" / "heal.yaml"
        assert manifest.exists()
        assert "mode: review-only" in manifest.read_text(encoding="utf-8")
        # dry-run 不改页面
        assert "DEAD0001" in page.read_text(encoding="utf-8")

    def test_heal_apply_rebinds_frontmatter(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        page = self._setup_stale_binding(temp_wiki_root)
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.main(
            ["zotero-heal", "--snapshot", "snap.yaml", "--apply"]
        )
        capsys.readouterr()

        assert rc == 0
        text = page.read_text(encoding="utf-8")
        assert "NEWKEY01" in text
        assert "DEAD0001" not in text
        log_text = (temp_wiki_root / "log.md").read_text(encoding="utf-8")
        assert "zotero-heal" in log_text

    def test_heal_requires_snapshot(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.main(["zotero-heal", "--snapshot", "missing.yaml"])
        assert rc == 1


class TestCmdZoteroAlias:
    def test_alias_render_with_default_pattern(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.main(
            [
                "zotero-alias",
                "--title",
                "LoRA: Low-Rank Adaptation",
                "--collection",
                "Machine Learning",
                "--collection",
                "LLM",
            ]
        )
        out = capsys.readouterr().out
        assert rc == 0
        assert "Machine-Learning/LLM/LoRA-Low-Rank-Adaptation" in out

    def test_alias_render_with_config_pattern(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        config = temp_wiki_root / "config.yaml"
        config.write_text(
            config.read_text(encoding="utf-8")
            + '\nzotero_import:\n  alias_pattern: "%y-%b"\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.main(
            [
                "zotero-alias",
                "--title",
                "Ignored",
                "--year",
                "2021",
                "--citekey",
                "hu2021lora",
            ]
        )
        out = capsys.readouterr().out
        assert rc == 0
        assert "2021-hu2021lora" in out

    def test_alias_render_rejects_unknown_wildcard(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.main(
            ["zotero-alias", "--title", "X", "--pattern", "%z"]
        )
        out = capsys.readouterr().out
        assert rc == 1
        assert "wildcard" in out


class TestCmdZoteroRelocate:
    def test_dry_run_reports_without_writing(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        import yaml

        from llm_wiki.zotero.local import LocalItem

        source = temp_wiki_root.parent / "relocate-source.pdf"
        source.write_bytes(b"pdf bytes")
        metadata_path = temp_wiki_root / "sources" / "zotero" / "metadata.yaml"
        metadata_path.parent.mkdir(parents=True)
        metadata_path.write_text(
            yaml.safe_dump(
                {
                    "version": 1,
                    "collections": [
                        {
                            "name": "Papers",
                            "items": [
                                {
                                    "title": "A Paper",
                                    "zotero_item_key": "ITEM0001",
                                    "attachments": [
                                        {
                                            "zotero_attachment_key": "ATTACH01",
                                            "local_path": str(source),
                                            "source_alias": "sources/zotero/paper.pdf",
                                            "filename": "relocate-source.pdf",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        managed = temp_wiki_root.parent / "managed"
        config = (temp_wiki_root / "config.yaml").read_text(encoding="utf-8")
        (temp_wiki_root / "config.yaml").write_text(
            config
            + f"\nzotero_relocation:\n  root: {str(managed)!r}\n  path_template: '%t'\n",
            encoding="utf-8",
        )

        class FakeWriter:
            def __init__(self, *args, **kwargs):
                self.item = LocalItem(
                    key="ATTACH01",
                    version=1,
                    data={
                        "key": "ATTACH01",
                        "itemType": "attachment",
                        "linkMode": "linked_file",
                        "path": str(source),
                        "parentItem": "ITEM0001",
                        "title": "A Paper",
                        "date": "2024",
                        "filename": "relocate-source.pdf",
                    },
                )

            async def get_item(self, item_key):
                return self.item

            async def aclose(self):
                return None

        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        monkeypatch.setattr("llm_wiki.zotero.local.LocalZoteroWriter", FakeWriter)
        args = _args(
            metadata="sources/zotero/metadata.yaml",
            root=None,
            storage_root=None,
            pattern=None,
            item_keys=None,
            attachment_keys=None,
            apply=False,
            delete_source=False,
            memory_authorize=False,
            app_name="llm-wiki",
            report_out="temp/zotero-relocate.yaml",
        )

        rc = agent_bridge_module.cmd_zotero_relocate(args)
        out = capsys.readouterr().out

        assert rc == 0
        assert "Dry-run only" in out
        assert (temp_wiki_root / "temp" / "zotero-relocate.yaml").exists()
        assert not managed.exists()
