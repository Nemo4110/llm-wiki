"""
Shared test fixtures for llm-wiki test suite.

Supports both full-suite runs (`pytest tests/`) and per-module runs
(`pytest tests/test_core.py`).
"""

import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Ensure project root is in path so `from src.llm_wiki` works when
# agent-bridge.py is imported dynamically.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))


# Lazy imports to avoid loading before path is set
@pytest.fixture
def WikiManager():
    from llm_wiki.core import WikiManager as WM
    return WM


def _make_page_content(title, body, tags=None, status="active", created=None, updated=None):
    today = (created or datetime.now()).strftime("%Y-%m-%d")
    up = (updated or datetime.now()).strftime("%Y-%m-%d")
    tags_yaml = "\n".join(f'  - "{t}"' for t in (tags or []))
    return f"""---
created: "{today}"
updated: "{up}"
tags:
{tags_yaml}
status: "{status}"
---

# {title}

{body}
"""


@pytest.fixture
def temp_wiki_root():
    """Create a temporary project root with a minimal wiki structure."""
    tmp = Path(tempfile.mkdtemp(prefix="llm-wiki-test-"))
    wiki_dir = tmp / "wiki"
    wiki_dir.mkdir()
    (tmp / "CLAUDE.md").write_text("# Test Wiki\n", encoding="utf-8")

    # Default config with linking enabled (deep_mode allows all strategies for tests)
    config = """linking:
  enabled: true
  light_mode:
    top_k: 5
    min_score: 0.3
    keyword_weight: 0.6
    link_weight: 0.4
  deep_mode:
    top_k: 10
    min_score: 0.2
    strategies_allowed:
      - link_only
      - append_related
      - append_section
      - update_concept
"""
    (tmp / "config.yaml").write_text(config, encoding="utf-8")

    # Sample pages — strong cross-links so relation discovery finds matches
    pages = [
        ("Transformer", "Self-attention mechanism for NLP. Related to [[LoRA]] fine-tuning method.", ["AI/ML", "NLP"]),
        ("LoRA", "Low-rank adaptation for fine-tuning. Uses [[Transformer]] architecture.", ["AI/ML", "NLP"]),
        ("Docker", "Containerization technology.", ["DevOps", "Container"]),
    ]
    for title, body, tags in pages:
        (wiki_dir / f"{title}.md").write_text(
            _make_page_content(title, body, tags), encoding="utf-8"
        )

    (wiki_dir / "index.md").write_text("# Wiki Index\n", encoding="utf-8")

    yield tmp

    shutil.rmtree(tmp)


@pytest.fixture
def wiki_manager(temp_wiki_root, WikiManager):
    return WikiManager(temp_wiki_root / "wiki")


@pytest.fixture
def agent_bridge_module():
    """Dynamically import agent-bridge.py (filename contains a hyphen)."""
    import importlib.util

    script_path = PROJECT_ROOT / "scripts" / "agent-bridge.py"
    spec = importlib.util.spec_from_file_location("agent_bridge", str(script_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["agent_bridge"] = mod
    spec.loader.exec_module(mod)
    return mod
