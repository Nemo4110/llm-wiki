"""
Tests for capabilities.py - declarative capability contracts
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from llm_wiki.capabilities import (
    CapabilityError,
    check_enabled,
    check_write_paths,
    get_capability,
)


class TestDefaultContracts:
    """每个 bridge 命令都有默认契约"""

    def test_every_command_has_a_declaration(self):
        for command in ("check", "status", "lint", "link", "relink", "query",
                        "merge", "index", "apply-bundle", "zotero-plan", "zotero-refresh",
                        "zotero-writeback", "zotero-ingest-verify"):
            cap = get_capability(command)
            assert cap.command == command

    def test_read_only_commands_have_no_write_scope(self):
        for command in ("check", "status", "lint", "link", "query"):
            assert get_capability(command).write_scope == ()

    def test_apply_bundle_scope_covers_wiki_and_log(self):
        cap = get_capability("apply-bundle")
        assert "wiki/" in cap.write_scope
        assert "log.md" in cap.write_scope

    def test_zotero_network_commands_are_explicit(self):
        assert get_capability("zotero-refresh").network is True
        assert get_capability("zotero-writeback").network is True
        assert get_capability("zotero-ingest-verify").network is False
        for command in ("check", "status", "lint", "link", "merge", "apply-bundle"):
            assert get_capability(command).network is False


class TestWritePathEnforcement:
    """check_write_paths:写入路径必须落在声明的 write_scope 内"""

    def test_allows_paths_inside_scope(self):
        check_write_paths("apply-bundle", [Path("wiki/New.md"), Path("log.md")])

    def test_rejects_sources_writes(self):
        with pytest.raises(CapabilityError, match="sources"):
            check_write_paths("apply-bundle", [Path("sources/paper.pdf")])

    def test_rejects_repo_code_writes(self):
        with pytest.raises(CapabilityError, match="write_scope"):
            check_write_paths("apply-bundle", [Path("src/llm_wiki/core.py")])

    def test_rejects_writes_for_read_only_command(self):
        with pytest.raises(CapabilityError):
            check_write_paths("lint", [Path("wiki/X.md")])


class TestConfigOverrides:
    """config.yaml 的 capabilities 段:只允许收紧,不允许放宽"""

    def test_disable_command(self):
        config = {"capabilities": {"apply-bundle": {"enabled": False}}}
        with pytest.raises(CapabilityError, match="disabled"):
            check_enabled("apply-bundle", config)

    def test_enabled_by_default(self):
        check_enabled("apply-bundle", {})

    def test_narrow_write_scope(self):
        config = {"capabilities": {"apply-bundle": {"write_scope": ["wiki/"]}}}
        check_write_paths("apply-bundle", [Path("wiki/New.md")], config)
        with pytest.raises(CapabilityError):
            check_write_paths("apply-bundle", [Path("log.md")], config)

    def test_widening_write_scope_rejected(self):
        config = {"capabilities": {"apply-bundle": {"write_scope": ["wiki/", "sources/"]}}}
        with pytest.raises(CapabilityError, match="widen"):
            check_write_paths("apply-bundle", [Path("wiki/New.md")], config)

    def test_unknown_command_override_rejected(self):
        config = {"capabilities": {"not-a-command": {"enabled": False}}}
        with pytest.raises(CapabilityError, match="unknown"):
            get_capability("apply-bundle", config)
