"""
Tests for scripts/agent-bridge.py — all 8 subcommands.

Run individually:
    pytest tests/test_agent_bridge.py -v

Note: agent-bridge.py is imported dynamically (filename contains a hyphen).
"""

import argparse
import re
import sys
from datetime import datetime, timedelta
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

    def test_ready_when_wiki_exists(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.cmd_check(_args())
        out = capsys.readouterr().out
        assert rc == 0
        assert "[READY]" in out
        assert "Transformer" in out

    def test_not_ready_without_wiki(self, agent_bridge_module, monkeypatch, capsys, tmp_path):
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

    def test_link_not_found(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        args = _args(source="NonExistent", mode="light", max_related=5)
        rc = agent_bridge_module.cmd_link(args)
        out = capsys.readouterr().out
        assert rc == 1
        assert "not found" in out.lower()

    def test_link_no_relations(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
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
    def test_relink_finds_new_pages(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        today = datetime.now().strftime("%Y-%m-%d")
        args = _args(since=today, mode="light", dry_run=True)
        rc = agent_bridge_module.cmd_relink(args)
        out = capsys.readouterr().out
        assert rc == 0
        assert "Global Relink Report" in out

    def test_relink_invalid_date(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        args = _args(since="not-a-date", mode="light", dry_run=True)
        rc = agent_bridge_module.cmd_relink(args)
        out = capsys.readouterr().out
        assert rc == 1
        assert "Invalid date" in out

    def test_relink_no_new_pages(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        future = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        args = _args(since=future, mode="light", dry_run=True)
        rc = agent_bridge_module.cmd_relink(args)
        out = capsys.readouterr().out
        assert rc == 0
        assert "No new pages" in out


class TestCmdLint:
    def test_lint_reports_issues(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
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
    def test_status_shows_overview(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.cmd_status(_args())
        out = capsys.readouterr().out
        assert rc == 0
        assert "Wiki Status" in out
        assert "Transformer" in out or "Total Pages" in out

    def test_status_no_wiki(self, agent_bridge_module, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", tmp_path)
        rc = agent_bridge_module.cmd_status(_args())
        out = capsys.readouterr().out
        assert rc == 1


class TestCmdMerge:
    def test_merge_dry_run(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
        from llm_wiki.core import WikiManager
        wiki = WikiManager(temp_wiki_root / "wiki")
        wiki.create_page(
            "SourcePage",
            "# SourcePage\n\nSource content.",
            {"created": "2026-04-01", "status": "active"},
        )
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        args = _args(source="SourcePage", target="Transformer", strategy="link_only", dry_run=True)
        rc = agent_bridge_module.cmd_merge(args)
        out = capsys.readouterr().out
        assert rc == 0
        assert "dry-run" in out.lower() or "Dry-run" in out
        # File should NOT be modified
        page = wiki.get_page("Transformer")
        assert "SourcePage" not in page.content

    def test_merge_source_not_found(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        args = _args(source="Missing", target="Transformer", strategy="link_only", dry_run=True)
        rc = agent_bridge_module.cmd_merge(args)
        out = capsys.readouterr().out
        assert rc == 1
        assert "not found" in out.lower()

    def test_merge_target_not_found(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        args = _args(source="Transformer", target="Missing", strategy="link_only", dry_run=True)
        rc = agent_bridge_module.cmd_merge(args)
        out = capsys.readouterr().out
        assert rc == 1

    def test_merge_strategy_not_allowed(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
        # Update config to remove update_concept from allowed strategies
        config_text = (temp_wiki_root / "config.yaml").read_text(encoding="utf-8")
        config_text = config_text.replace("      - update_concept\n", "")
        (temp_wiki_root / "config.yaml").write_text(config_text, encoding="utf-8")

        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        args = _args(source="Transformer", target="LoRA", strategy="update_concept", dry_run=True)
        rc = agent_bridge_module.cmd_merge(args)
        out = capsys.readouterr().out
        assert rc == 1
        assert "not allowed" in out.lower()


class TestCmdQuery:
    def test_query_fallback_when_embedding_disabled(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
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
        out = capsys.readouterr().out
        assert rc == 1


class TestCmdIndex:
    def test_index_disabled(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
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
        out = capsys.readouterr().out
        assert rc == 1


class TestMain:
    def test_main_dispatch_check(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
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

    def test_main_link_with_args(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        rc = agent_bridge_module.main(["link", "--source", "Transformer", "--mode", "light"])
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
        assert "llm-wiki:Graph-Neural-Networks" in out
        assert "llm-wiki:ingested" in out
        assert "GNN" in out
        assert "Read-only plan" in out
        assert snapshot.read_text(encoding="utf-8") == original

        rc = agent_bridge_module.main([
            "zotero-plan",
            "--snapshot",
            "gnn.yaml",
            "--manifest-out",
            "temp/gnn-manifest.yaml",
        ])
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
        rc = agent_bridge_module.main([
            "zotero-plan",
            "--snapshot",
            "gnn.yaml",
            "--manifest-out",
            "outside.yaml",
        ])
        out = capsys.readouterr().out

        assert rc == 1
        assert "must stay under" in out


class TestCmdZoteroRefresh:
    def test_refresh_dry_run_writes_review_manifest_under_temp(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        from src.llm_wiki.zotero_refresh import RefreshMutation, RefreshReport
        import src.llm_wiki.zotero_refresh as refresh_module

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
        rc = agent_bridge_module.main([
            "zotero-refresh",
            "--collection-key",
            "A9VNJUPI",
            "--manifest-out",
            "temp/refresh.yaml",
        ])
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
        rc = agent_bridge_module.main([
            "zotero-refresh",
            "--collection-key",
            "A9VNJUPI",
        ])
        out = capsys.readouterr().out

        assert rc == 1
        assert "must stay under" in out

    def test_refresh_rejects_manifest_outside_temp(
        self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys
    ):
        from src.llm_wiki.zotero_refresh import RefreshReport
        import src.llm_wiki.zotero_refresh as refresh_module

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
        rc = agent_bridge_module.main([
            "zotero-refresh",
            "--collection-key",
            "A9VNJUPI",
            "--manifest-out",
            "outside.yaml",
        ])
        out = capsys.readouterr().out

        assert rc == 1
        assert "must stay under" in out


class TestCmdApplyBundle:
    """apply-bundle 子命令:事务化多文件写入"""

    def _make_bundle(self, root: Path, update_hash: str) -> Path:
        import hashlib
        temp = root / "temp"
        temp.mkdir(exist_ok=True)
        (temp / "draft-page.md").write_text("---\ntags: []\n---\n\n# NewPage\n\nbody\n", encoding="utf-8")
        (temp / "draft-index.md").write_text("# Wiki Index\n\n- [[NewPage]]\n", encoding="utf-8")
        (temp / "draft-log.md").write_text("# Log\n\n## [2026-08-24] ingest | NewPage\n", encoding="utf-8")
        manifest = temp / "tx-bundle.yaml"
        manifest.write_text(f"""
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
""", encoding="utf-8")
        (root / "log.md").write_text("# Log\n", encoding="utf-8")
        return manifest

    def _index_hash(self, root: Path) -> str:
        import hashlib
        content = (root / "wiki" / "index.md").read_text(encoding="utf-8")
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def test_dry_run_previews_without_writing(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        manifest = self._make_bundle(temp_wiki_root, self._index_hash(temp_wiki_root))

        rc = agent_bridge_module.cmd_apply_bundle(_args(manifest=str(manifest), dry_run=True))
        out = capsys.readouterr().out

        assert rc == 0
        assert "Transaction Preview" in out
        assert "wiki/NewPage.md" in out
        assert not (temp_wiki_root / "wiki" / "NewPage.md").exists()
        assert (temp_wiki_root / "log.md").read_text(encoding="utf-8") == "# Log\n"

    def test_dry_run_reports_current_hash_when_missing(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        manifest = self._make_bundle(temp_wiki_root, self._index_hash(temp_wiki_root))
        # 去掉 update 的 expected_sha256,模拟 Agent 先探测哈希
        text = manifest.read_text(encoding="utf-8")
        text = "\n".join(l for l in text.split("\n") if "expected_sha256" not in l)
        manifest.write_text(text, encoding="utf-8")

        rc = agent_bridge_module.cmd_apply_bundle(_args(manifest=str(manifest), dry_run=True))
        out = capsys.readouterr().out

        assert rc == 0
        assert "current sha256" in out
        assert self._index_hash(temp_wiki_root) in out

    def test_apply_writes_all_files(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        manifest = self._make_bundle(temp_wiki_root, self._index_hash(temp_wiki_root))

        rc = agent_bridge_module.cmd_apply_bundle(_args(manifest=str(manifest), dry_run=False))
        out = capsys.readouterr().out

        assert rc == 0
        assert "Applied" in out
        assert (temp_wiki_root / "wiki" / "NewPage.md").exists()
        assert "[[NewPage]]" in (temp_wiki_root / "wiki" / "index.md").read_text(encoding="utf-8")
        assert "ingest | NewPage" in (temp_wiki_root / "log.md").read_text(encoding="utf-8")

    def test_apply_with_stale_hash_writes_nothing(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)
        manifest = self._make_bundle(temp_wiki_root, "0" * 64)

        rc = agent_bridge_module.cmd_apply_bundle(_args(manifest=str(manifest), dry_run=False))
        out = capsys.readouterr().out

        assert rc == 1
        assert "Hash mismatch" in out or "hash mismatch" in out
        assert not (temp_wiki_root / "wiki" / "NewPage.md").exists()
        assert (temp_wiki_root / "log.md").read_text(encoding="utf-8") == "# Log\n"

    def test_missing_manifest_returns_error(self, agent_bridge_module, temp_wiki_root, monkeypatch, capsys):
        monkeypatch.setattr(agent_bridge_module, "PROJECT_ROOT", temp_wiki_root)

        rc = agent_bridge_module.cmd_apply_bundle(
            _args(manifest=str(temp_wiki_root / "nope.yaml"), dry_run=False))
        out = capsys.readouterr().out

        assert rc == 1
        assert "Error" in out
