"""
Tests for llm_wiki.agent_logger — execution traceability and log formatting.

Run individually:
    pytest tests/test_agent_logger.py -v
"""

import logging
from io import StringIO
from pathlib import Path

import pytest

from llm_wiki.agent_logger import (
    setup_agent_logging,
    get_logger,
    _AgentLogFilter,
    _AGENT_LOG_FORMAT,
)


class TestSetupAgentLogging:
    def test_idempotent(self):
        """Calling setup_agent_logging twice should not add duplicate handlers."""
        setup_agent_logging()
        logger = logging.getLogger("llm_wiki")
        first_count = len(logger.handlers)
        setup_agent_logging()
        second_count = len(logger.handlers)
        assert first_count == second_count

    def test_logs_to_stderr(self, capsys):
        """Logs should appear on stderr (captured by capsys after handler reconfiguration)."""
        setup_agent_logging()
        # Re-point handler to capsys's stderr so we can assert
        logger = logging.getLogger("llm_wiki")
        for h in logger.handlers:
            h.stream = capsys._capture.err  # pytest's captured stderr
        get_logger("test_output").info("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.err


class TestLogFormat:
    def _capture_formatted(self, level, msg):
        """Helper: emit a log through our formatter into a StringIO."""
        setup_agent_logging()
        buf = StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(logging.Formatter(_AGENT_LOG_FORMAT))
        logger = get_logger("test_format")
        logger.addHandler(handler)
        logger.log(level, msg)
        logger.removeHandler(handler)
        return buf.getvalue()

    def test_contains_level(self):
        output = self._capture_formatted(logging.INFO, "formatted")
        assert "[INFO]" in output

    def test_contains_file_and_line(self):
        output = self._capture_formatted(logging.DEBUG, "linecheck")
        assert "test_agent_logger.py:" in output

    def test_contains_func_name(self):
        # Directly format a LogRecord to verify funcName appears
        formatter = logging.Formatter(_AGENT_LOG_FORMAT)
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname=__file__,
            lineno=1,
            msg="funccheck",
            args=(),
            exc_info=None,
            func="my_test_function",
        )
        output = formatter.format(record)
        assert "my_test_function()" in output

    def test_format_string_structure(self):
        assert "%(levelname)s" in _AGENT_LOG_FORMAT
        assert "%(pathname)s:%(lineno)d" in _AGENT_LOG_FORMAT
        assert "%(funcName)s()" in _AGENT_LOG_FORMAT
        assert "%(message)s" in _AGENT_LOG_FORMAT


class TestAgentLogFilter:
    def test_pathname_relative_to_project(self):
        project = Path("/fake/project")
        filt = _AgentLogFilter(project)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=str(project / "src" / "foo.py"),
            lineno=10,
            msg="hello",
            args=(),
            exc_info=None,
        )
        filt.filter(record)
        assert record.pathname == "src/foo.py"

    def test_pathname_unchanged_when_outside_project(self):
        project = Path("/fake/project")
        filt = _AgentLogFilter(project)
        outside = "/outside/file.py"
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=outside,
            lineno=10,
            msg="hello",
            args=(),
            exc_info=None,
        )
        filt.filter(record)
        assert record.pathname == outside


class TestGetLogger:
    def test_namespace(self):
        logger = get_logger("core")
        assert logger.name == "llm_wiki.core"

    def test_child_logger_inherits_handlers(self):
        setup_agent_logging()
        parent = logging.getLogger("llm_wiki")
        child = get_logger("child_test")
        assert child.handlers == []  # child shouldn't have its own handlers
        assert child.parent == parent
