"""
llm-wiki init — scaffold a knowledge-base directory without a git clone.

The console entry point is installed via `uv tool install` (or pipx), so the
user may have no project checkout at all. `init` materializes the runtime
skeleton — wiki/, sources/, AGENTS.md, CLAUDE.md, config.yaml.example — from
templates shipped inside the wheel (llm_wiki/templates/).
"""

from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path

WIKI_INDEX = """# Wiki Index

> Knowledge base entry point. Start here to explore or add new content.

## Recent Activity

See [log.md](../log.md) for full history.

## Quick Start

1. Add source materials to `sources/`.
2. Ask your agent: "Ingest sources/[filename] into wiki".
3. Explore and query the generated knowledge.

## Status

- Empty: waiting for first ingest.

---

*Last updated: {today}*
"""

LOG_MD = "# Log\n\nNo activity yet.\n"

# A real file CLAUDE.md is used instead of a symlink so the scaffold works on
# Windows without Developer Mode. It points the agent at the canonical
# AGENTS.md and satisfies find_wiki_root()'s CLAUDE.md sentinel.
CLAUDE_MD = """# CLAUDE.md

> This knowledge base follows the llm-wiki unified agent protocol.
> **Read [`AGENTS.md`](AGENTS.md) — it is the canonical protocol and entry point.**

All agent behavior, ingest/query protocol, source-integrity rules, and tool
selection guidance are defined in `AGENTS.md`. Treat it as the single source of
truth for this wiki.
"""


def _template_text(name: str) -> str:
    return (
        resources.files("llm_wiki.templates")
        .joinpath(name)
        .read_text(encoding="utf-8")
    )


def _write(path: Path, content: str, force: bool) -> bool:
    """Write content to path. Returns True if written, False if skipped."""
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _copy_template(template_name: str, dest: Path, force: bool) -> bool:
    if dest.exists() and not force:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_template_text(template_name), encoding="utf-8")
    return True


def scaffold(target_dir: Path, force: bool = False) -> list[str]:
    """Create the wiki skeleton under target_dir. Returns human actions taken."""
    from datetime import date

    target_dir = target_dir.expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    actions: list[str] = []

    def mark(created: bool, label: str) -> None:
        actions.append(("created" if created else "kept   ") + f"  {label}")

    # Protocol + entry-point sentinel
    mark(_copy_template("AGENTS.md", target_dir / "AGENTS.md", force), "AGENTS.md")
    mark(_write(target_dir / "CLAUDE.md", CLAUDE_MD, force), "CLAUDE.md")
    mark(
        _copy_template(
            "config.yaml.example", target_dir / "config.yaml.example", force
        ),
        "config.yaml.example",
    )

    # Knowledge-base dirs
    mark(
        _write(
            target_dir / "wiki" / "index.md",
            WIKI_INDEX.format(today=date.today().isoformat()),
            force,
        ),
        "wiki/index.md",
    )
    mark(
        _copy_template(
            "sources-README.md", target_dir / "sources" / "README.md", force
        ),
        "sources/README.md",
    )
    mark(
        _copy_template(
            "page_template.md",
            target_dir / "assets" / "page_template.md",
            force,
        ),
        "assets/page_template.md",
    )
    mark(_write(target_dir / "log.md", LOG_MD, force), "log.md")

    return actions
