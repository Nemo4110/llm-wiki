"""Backward-compatibility module alias. Use src.llm_wiki.zotero.relocate instead."""
from __future__ import annotations

import sys
import importlib

try:
    _mod = importlib.import_module("llm_wiki.zotero.relocate")
except ImportError:
    _mod = importlib.import_module("src.llm_wiki.zotero.relocate")

# Re-export and replace module in sys.modules
for _k, _v in _mod.__dict__.items():
    if not _k.startswith("__"):
        globals()[_k] = _v

sys.modules[__name__] = _mod
