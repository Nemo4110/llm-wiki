#!/usr/bin/env python3
"""
Agent Bridge — Unified entry point for LLM-Wiki operations.
This is a lightweight compatibility shim delegating to src.llm_wiki.cli.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Ensure project root and src/ are on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    import llm_wiki.cli as _cli
except ImportError:
    import src.llm_wiki.cli as _cli

# Re-export all functions and constants from cli module
for _k, _v in _cli.__dict__.items():
    if not _k.startswith("__"):
        globals()[_k] = _v

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
