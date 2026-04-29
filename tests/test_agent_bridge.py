"""
Tests for scripts/agent-bridge.py — all 8 subcommands.

Run individually:
    pytest tests/test_agent_bridge.py -v

Note: agent-bridge.py is imported dynamically (filename contains a hyphen).
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest


# Helper to build argparse.Namespace for each subcommand
def _args(**kwargs):
    return argparse.Namespace(**kwargs)


class TestCmdCheck:
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
