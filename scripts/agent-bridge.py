#!/usr/bin/env python3
"""
Agent Bridge — Unified entry point for LLM-Wiki operations.

This script is the ONLY tool an Agent needs to remember when working
with llm-wiki. It automatically detects the runtime environment,
chooses the best execution path (direct library call or CLI wrapper),
and always produces structured Markdown output designed for both
human readability and machine parsing.

Design principles:
  1. Zero-config for the Agent: run `python scripts/agent-bridge.py <task>`
  2. Environment auto-detection: finds venv, detects deps, probes config
  3. Structured Markdown output: no JSON, clear sections, actionable markers
  4. Execution traceability: every internal step is logged to stderr
     with file:line precision so the Agent sees the full pipeline.

Usage:
    python scripts/agent-bridge.py check
    python scripts/agent-bridge.py link --source "NewPage" --mode light
    python scripts/agent-bridge.py relink --since 2026-04-20 --mode deep --dry-run
    python scripts/agent-bridge.py lint
    python scripts/agent-bridge.py status
    python scripts/agent-bridge.py query "What is LoRA?" --semantic
    python scripts/agent-bridge.py zotero-plan --snapshot temp/zotero-snapshot.yaml
    python scripts/agent-bridge.py merge --source "NewPage" --target "OldPage" \
        --strategy append_related --dry-run
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Ensure we can import src.llm_wiki when run from project root
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Logging setup (must happen before any other imports that might log)
# ---------------------------------------------------------------------------
from src.llm_wiki.agent_logger import setup_agent_logging, get_logger

setup_agent_logging(PROJECT_ROOT)
LOG = get_logger("agent_bridge")

# ---------------------------------------------------------------------------
# Environment detection helpers
# ---------------------------------------------------------------------------


def _probe_imports(py_path: str) -> bool:
    """True if py_path can import llm-wiki either as an installed package
    (llm_wiki, from `uv tool install`) or from a source checkout (src.llm_wiki)."""
    probe = "import importlib.util, sys; sys.exit(0 if (importlib.util.find_spec('llm_wiki') or importlib.util.find_spec('src.llm_wiki')) else 1)"
    result = subprocess.run(
        [py_path, "-B", "-c", probe],
        capture_output=True,
        cwd=PROJECT_ROOT,
    )
    return result.returncode == 0


def _find_python() -> Tuple[str, bool]:
    """
    Find the best Python interpreter for running llm-wiki code.
    Returns (python_path, is_venv).
    """
    candidates: List[Tuple[str, bool]] = []

    # 1. conda environment
    conda_prefix = os.environ.get("CONDA_PREFIX", "")
    if conda_prefix:
        py = Path(conda_prefix) / ("python.exe" if sys.platform == "win32" else "bin/python")
        if py.exists():
            candidates.append((str(py), True))

    # 2. local virtual environments (created by `uv venv` or python -m venv)
    for venv_name in (".venv", "venv"):
        venv = PROJECT_ROOT / venv_name
        if not venv.exists():
            continue
        if sys.platform == "win32":
            py = venv / "Scripts" / "python.exe"
        else:
            py = venv / "bin" / "python"
        if py.exists():
            candidates.append((str(py), True))

    # 3. current interpreter — under `uv run` or an activated uv tool venv this
    #    is already an environment that can import llm_wiki.
    candidates.append((sys.executable, False))

    # Pick first that can import the library (installed or source layout)
    for py_path, is_venv in candidates:
        if _probe_imports(py_path):
            LOG.debug("Selected Python: %s (venv=%s)", py_path, is_venv)
            return py_path, is_venv

    LOG.warning("No Python interpreter found that can import llm_wiki or src.llm_wiki")
    return sys.executable, False


def _detect_environment() -> Dict[str, Any]:
    """Probe the runtime environment and return a structured report."""
    LOG.info("Probing environment...")

    python_path, is_venv = _find_python()
    env = {
        "project_root": str(PROJECT_ROOT),
        "python_path": python_path,
        "is_venv": is_venv,
        "platform": sys.platform,
    }

    # Can we import the library?
    try:
        import src.llm_wiki
        from src.llm_wiki.config import load_config
        from src.llm_wiki.core import WikiManager, find_wiki_root

        env["library_available"] = True
    except Exception as e:
        LOG.error("Cannot import src.llm_wiki: %s", e)
        env["library_available"] = False
        env["error"] = str(e)
        return env

    # Wiki root
    wiki_root = find_wiki_root(PROJECT_ROOT)
    env["wiki_root"] = str(wiki_root) if wiki_root else None

    if not wiki_root:
        env["wiki_ready"] = False
        return env

    # Config
    try:
        config = load_config(wiki_root)
        env["config"] = config
    except Exception as e:
        LOG.error("Failed to load config: %s", e)
        env["config"] = None

    # Wiki pages
    try:
        wiki = WikiManager(wiki_root / "wiki")
        pages = wiki.list_pages()
        env["wiki_ready"] = True
        env["page_count"] = len(pages)
        env["pages"] = [p.title for p in pages]
    except Exception as e:
        LOG.error("Failed to list wiki pages: %s", e)
        env["wiki_ready"] = False

    LOG.info("Environment probe complete: library=%s wiki_ready=%s pages=%s",
             env.get("library_available"), env.get("wiki_ready"), env.get("page_count"))
    return env


# ---------------------------------------------------------------------------
# Markdown output helpers
# ---------------------------------------------------------------------------


def _md_header(title: str, level: int = 2) -> str:
    return f"{'#' * level} {title}"


def _md_table(
    headers: List[str],
    rows: List[List[str]],
    alignments: Optional[List[str]] = None,
) -> str:
    resolved_alignments = alignments or ["left"] * len(headers)
    separators = {
        "left": "---",
        "right": "---:",
        "center": ":---:",
    }
    separator_row = [separators[value] for value in resolved_alignments]

    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(separator_row) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _md_table_cell(value: Any) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").replace("|", r"\|")


def _md_code_block(content: str, lang: str = "") -> str:
    return f"```{lang}\n{content}\n```"


def _md_action(text: str) -> str:
    """Mark an item as actionable for the Agent."""
    return f"> **[ACTION]** {text}"


def _md_info(text: str) -> str:
    return f"> **{text}**"


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------


def cmd_check(args: argparse.Namespace) -> int:
    """Environment self-check."""
    env = _detect_environment()

    lines: List[str] = []
    lines.append(_md_header("Agent Bridge Environment Check"))
    lines.append("")

    # Summary
    lib_ok = env.get("library_available", False)
    wiki_ok = env.get("wiki_ready", False)
    if lib_ok and wiki_ok:
        status = "[READY]"
    elif lib_ok:
        status = "[PARTIAL]"
    else:
        status = "[NOT READY]"
    lines.append(_md_info(f"Status: {status}"))
    lines.append("")

    # Environment table
    lines.append(_md_header("Runtime", level=3))
    rows = [
        ["Project Root", str(env.get("project_root", "N/A"))],
        ["Python", str(env.get("python_path", "N/A"))],
        ["Virtual Env", "Yes" if env.get("is_venv") else "No"],
        ["Platform", str(env.get("platform", "N/A"))],
        ["Library Import", "OK" if lib_ok else "FAIL"],
    ]
    lines.append(_md_table(["Key", "Value"], rows))
    lines.append("")

    # Wiki status
    if wiki_ok:
        lines.append(_md_header("Wiki", level=3))
        wiki_rows = [
            ["Wiki Root", str(env.get("wiki_root", "N/A"))],
            ["Page Count", str(env.get("page_count", 0))],
        ]
        config = env.get("config")
        if config:
            emb = config.get("embedding", {})
            linking = config.get("linking", {})
            wiki_rows.append(["Embedding", "Enabled" if emb.get("enabled") else "Disabled"])
            wiki_rows.append(["Provider", str(emb.get("provider", "N/A"))])
            wiki_rows.append(["Linking", "Enabled" if linking.get("enabled") else "Disabled"])
        lines.append(_md_table(["Key", "Value"], wiki_rows))
        lines.append("")

        # Page list (first 20)
        pages = env.get("pages", [])[:20]
        if pages:
            lines.append(_md_header("Pages", level=3))
            lines.append(_md_code_block("\n".join(f"- [[{p}]]" for p in pages)))
            lines.append("")
    else:
        lines.append(_md_header("Wiki", level=3))
        lines.append(_md_info("Wiki not initialized or inaccessible."))
        if env.get("error"):
            lines.append(_md_code_block(str(env["error"])))
        lines.append("")

    # Actionable
    lines.append(_md_header("Next Steps", level=3))
    if not lib_ok:
        lines.append(_md_action("Install dependencies: `pip install -r src/requirements.txt`"))
    elif not wiki_ok:
        lines.append(_md_action("Initialize wiki: ensure `wiki/` and `CLAUDE.md` exist"))
    else:
        lines.append(_md_action("Environment ready. Proceed with wiki tasks."))

    print("\n".join(lines))
    return 0 if (lib_ok and wiki_ok) else 1


def cmd_link(args: argparse.Namespace) -> int:
    """Run relation discovery between a new page and existing wiki."""
    LOG.info("cmd_link: source=%s mode=%s", args.source, args.mode)

    from src.llm_wiki.config import load_config
    from src.llm_wiki.core import WikiManager, find_wiki_root
    from src.llm_wiki.linker import KnowledgeLinker
    from src.llm_wiki.embeddings import create_provider
    from src.llm_wiki.retrieval import EmbeddingIndex

    wiki_root = find_wiki_root(PROJECT_ROOT)
    if not wiki_root:
        print(_md_info("Error: Cannot find wiki root. Ensure CLAUDE.md exists."))
        return 1

    config = load_config(wiki_root)

    # Auto-select mode when not explicitly specified
    if args.mode is None:
        emb_cfg = config.get("embedding", {})
        if emb_cfg.get("enabled", False):
            try:
                provider = create_provider(config)
                if provider:
                    args.mode = "deep"
                    LOG.info("Embedding available, auto-selecting deep mode")
                else:
                    args.mode = "light"
            except Exception:
                args.mode = "light"
        else:
            args.mode = "light"

    wiki = WikiManager(wiki_root / "wiki")
    source_page = wiki.get_page(args.source)
    if not source_page:
        print(_md_info(f"Error: Source page not found: `{args.source}`"))
        return 1

    LOG.info("Loaded source page: %s (tags=%s)", source_page.title, source_page.tags)

    # Initialize linker
    linker = KnowledgeLinker(wiki)
    if args.mode == "deep":
        emb_cfg = config.get("embedding", {})
        if emb_cfg.get("enabled", False):
            try:
                provider = create_provider(config)
                if provider:
                    linker.index = EmbeddingIndex(wiki, provider)
                    LOG.info("Embedding index attached for deep mode")
            except Exception as e:
                LOG.warning("Embedding index unavailable: %s", e)

    # Run discovery
    LOG.info("Running relation discovery (mode=%s, top_k=%d)...", args.mode, args.max_related)
    if args.mode == "light":
        light_cfg = config.get("linking", {}).get("light_mode", {})
        rels = linker.find_related(
            query=args.source,
            query_tags=source_page.tags,
            query_content=source_page.content,
            top_k=args.max_related,
            min_score=light_cfg.get("min_score", 0.3),
            use_embedding=light_cfg.get("vector_weight", 0) > 0,
            keyword_weight=light_cfg.get("keyword_weight", 0.6),
            vector_weight=light_cfg.get("vector_weight", 0.0),
            link_weight=light_cfg.get("link_weight", 0.4),
        )
    else:
        deep_cfg = config.get("linking", {}).get("deep_mode", {})
        rels = linker.find_related(
            query=args.source,
            query_tags=source_page.tags,
            query_content=source_page.content,
            top_k=args.max_related,
            min_score=deep_cfg.get("min_score", 0.2),
            use_embedding=True,
            keyword_weight=0.4,
            vector_weight=0.4,
            link_weight=0.2,
        )

    LOG.info("Found %d relations", len(rels))

    # Output structured markdown
    lines: List[str] = []
    lines.append(_md_header(f"Relation Discovery: {args.source}"))
    lines.append("")
    lines.append(_md_info(f"Mode: `{args.mode}` | Relations found: {len(rels)}"))
    lines.append("")

    if not rels:
        lines.append("No significant relations discovered.")
        print("\n".join(lines))
        return 0

    # Table of relations
    lines.append(_md_header("Relations", level=3))
    table_rows = []
    for r in rels:
        table_rows.append([
            f"[[{r.target}]]",
            f"{r.score:.2f}",
            r.relation_type.value.upper(),
            "; ".join(r.evidence) if r.evidence else "—",
        ])
    lines.append(_md_table(["Target", "Score", "Type", "Evidence"], table_rows))
    lines.append("")

    # Actionable section
    high = [r for r in rels if r.score >= 0.5]
    medium = [r for r in rels if 0.3 <= r.score < 0.5]

    lines.append(_md_header("Actionable Items", level=3))
    if high:
        lines.append(_md_info(f"High confidence (≥0.5): {len(high)}"))
        for r in high:
            lines.append(_md_action(
                f"Review relation to [[{r.target}]] (score={r.score:.2f}, type={r.relation_type.value})"
            ))
            lines.append(f"  - Suggested: {r.suggested_action}")
            lines.append(_md_code_block(
                f"python scripts/agent-bridge.py merge "
                f"--source \"{args.source}\" --target \"{r.target}\" "
                f"--strategy {r.relation_type.value} --dry-run",
                lang="bash",
            ))
        lines.append("")

    if medium:
        lines.append(_md_info(f"Medium confidence (0.3–0.5): {len(medium)}"))
        for r in medium:
            lines.append(f"- [[{r.target}]] — score={r.score:.2f} — consider manual review")
        lines.append("")

    print("\n".join(lines))
    return 0


def cmd_relink(args: argparse.Namespace) -> int:
    """Batch global relation discovery for recently added pages."""
    LOG.info("cmd_relink: since=%s mode=%s dry_run=%s", args.since, args.mode, args.dry_run)

    from src.llm_wiki.config import load_config
    from src.llm_wiki.core import WikiManager, find_wiki_root
    from src.llm_wiki.linker import KnowledgeLinker
    from src.llm_wiki.embeddings import create_provider
    from src.llm_wiki.retrieval import EmbeddingIndex

    wiki_root = find_wiki_root(PROJECT_ROOT)
    if not wiki_root:
        print(_md_info("Error: Cannot find wiki root."))
        return 1

    config = load_config(wiki_root)
    wiki = WikiManager(wiki_root / "wiki")
    all_pages = wiki.list_pages()

    # Filter new pages
    if args.since:
        try:
            since_date = datetime.strptime(args.since, "%Y-%m-%d")
        except ValueError:
            print(_md_info("Error: Invalid date format. Use YYYY-MM-DD."))
            return 1
    else:
        since_date = datetime.now() - timedelta(days=7)

    new_pages = [
        p for p in all_pages
        if p.frontmatter.get("created")
        and datetime.strptime(str(p.frontmatter.get("created")), "%Y-%m-%d") >= since_date
    ]

    LOG.info("Found %d new pages since %s", len(new_pages), since_date.date())

    lines: List[str] = []
    lines.append(_md_header("Global Relink Report"))
    lines.append("")
    lines.append(_md_info(f"Since: {since_date.date()} | New pages: {len(new_pages)} | Mode: `{args.mode}`"))
    lines.append("")

    if not new_pages:
        lines.append("No new pages found in the specified period.")
        print("\n".join(lines))
        return 0

    # List new pages
    lines.append(_md_header("New Pages", level=3))
    lines.append(_md_code_block("\n".join(f"- [[{p.title}]]" for p in new_pages)))
    lines.append("")

    # Initialize linker
    linker = KnowledgeLinker(wiki)
    if args.mode == "deep":
        emb_cfg = config.get("embedding", {})
        if emb_cfg.get("enabled", False):
            try:
                provider = create_provider(config)
                if provider:
                    linker.index = EmbeddingIndex(wiki, provider)
            except Exception as e:
                LOG.warning("Embedding unavailable: %s", e)

    # Run global discovery
    titles = [p.title for p in new_pages]
    top_k = config.get("linking", {}).get("deep_mode" if args.mode == "deep" else "light_mode", {}).get("top_k", 10)
    graph = linker.build_relation_graph(titles, mode=args.mode, top_k=top_k)

    LOG.info("Global discovery complete: %d relations", len(graph.relations))

    if not graph.relations:
        lines.append("No cross-page relations discovered.")
        print("\n".join(lines))
        return 0

    # Group by source
    by_source: Dict[str, List[Any]] = {}
    for rel in graph.relations:
        by_source.setdefault(rel.source, []).append(rel)

    lines.append(_md_header("Relations by Source Page", level=3))
    for src, rels in by_source.items():
        lines.append(f"\n#### [[{src}]]\n")
        rows = []
        for r in sorted(rels, key=lambda x: x.score, reverse=True):
            rows.append([f"[[{r.target}]]", f"{r.score:.2f}", r.relation_type.value.upper()])
        lines.append(_md_table(["Target", "Score", "Type"], rows))

    # Actionable
    lines.append("")
    lines.append(_md_header("Next Steps", level=3))
    if args.dry_run:
        lines.append(_md_action("This was a dry-run. Review relations above, then run without `--dry-run`."))
    else:
        lines.append(_md_action("For each high-confidence relation, run `merge` to apply changes."))
        lines.append(_md_code_block(
            "python scripts/agent-bridge.py merge --source <PAGE> --target <PAGE> --strategy <STRATEGY> --dry-run",
            lang="bash",
        ))

    print("\n".join(lines))
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    """Run wiki health check."""
    LOG.info("cmd_lint")

    from src.llm_wiki.config import load_config
    from src.llm_wiki.core import WikiManager, find_wiki_root

    wiki_root = find_wiki_root(PROJECT_ROOT)
    if not wiki_root:
        print(_md_info("Error: Cannot find wiki root."))
        return 1

    config = load_config(wiki_root)
    wiki = WikiManager(wiki_root / "wiki")
    depth_config = config.get("lint", {}).get("depth")
    issues = wiki.lint(depth_config, include_depth_details=True)
    LOG.info(
        "Lint complete: orphans=%d dead_links=%d stale=%d empty_pages=%d "
        "duplicate_titles=%d noncanonical_links=%d drafts=%d shallow_pages=%d",
        len(issues["orphans"]), len(issues["dead_links"]),
        len(issues["stale"]), len(issues["empty_pages"]),
        len(issues["duplicate_titles"]), len(issues["noncanonical_links"]),
        len(issues["drafts"]), len(issues["shallow_pages"]),
    )

    lines: List[str] = []
    lines.append(_md_header("Wiki Health Check"))
    lines.append("")

    has_issues = any(issues.values())
    if not has_issues:
        lines.append(_md_info("All checks passed. Wiki is healthy."))
        print("\n".join(lines))
        return 0

    lines.append(_md_header("Summary", level=3))
    lines.append(_md_table(
        ["Check", "Count", "Status"],
        [
            ["Orphan pages", str(len(issues["orphans"])), "⚠️" if issues["orphans"] else "✅"],
            ["Dead links", str(len(issues["dead_links"])), "⚠️" if issues["dead_links"] else "✅"],
            ["Stale pages", str(len(issues["stale"])), "⚠️" if issues["stale"] else "✅"],
            ["Empty pages", str(len(issues["empty_pages"])), "⚠️" if issues["empty_pages"] else "✅"],
            ["Duplicate titles", str(len(issues["duplicate_titles"])), "⚠️" if issues["duplicate_titles"] else "✅"],
            ["Non-canonical links", str(len(issues["noncanonical_links"])), "⚠️" if issues["noncanonical_links"] else "✅"],
            ["Draft pages", str(len(issues["drafts"])), "⚠️" if issues["drafts"] else "✅"],
            ["Shallow pages", str(len(issues["shallow_pages"])), "⚠️" if issues["shallow_pages"] else "✅"],
            ["Invalid status", str(len(issues["invalid_status"])), "⚠️" if issues["invalid_status"] else "✅"],
            ["Lifecycle mismatch", str(len(issues["lifecycle_mismatch"])), "⚠️" if issues["lifecycle_mismatch"] else "✅"],
            ["Claim issues", str(len(issues["claim_issues"])), "⚠️" if issues["claim_issues"] else "✅"],
        ],
    ))
    lines.append("")

    if issues["orphans"]:
        lines.append(_md_header("Orphan Pages (not referenced)", level=3))
        lines.append(_md_code_block("\n".join(f"- [[{p}]]" for p in issues["orphans"])))
        lines.append("")

    if issues["dead_links"]:
        lines.append(_md_header("Dead Links (target is not a wiki file stem)", level=3))
        lines.append(_md_code_block("\n".join(f"- [[{link}]]" for link in issues["dead_links"])))
        lines.append("")
        lines.append(_md_action("Create the missing canonical page file or rewrite the link target to an existing file stem."))
        lines.append("")

    if issues["stale"]:
        lines.append(_md_header("Stale Pages (>90 days since update)", level=3))
        lines.append(_md_code_block("\n".join(f"- [[{p}]]" for p in issues["stale"])))
        lines.append("")

    if issues["empty_pages"]:
        lines.append(_md_header("Empty Pages", level=3))
        lines.append(_md_code_block("\n".join(f"- [[{p}]]" for p in issues["empty_pages"])))
        lines.append("")
        lines.append(_md_action("Fill these pages with useful content or remove duplicate empty shells."))
        lines.append("")

    if issues["duplicate_titles"]:
        lines.append(_md_header("Duplicate Titles", level=3))
        lines.append(_md_code_block("\n".join(f"- {p}" for p in issues["duplicate_titles"])))
        lines.append("")
        lines.append(_md_action("Remove duplicate shell files or merge them into the canonical page file."))
        lines.append("")

    if issues["noncanonical_links"]:
        lines.append(_md_header("Non-Canonical Links", level=3))
        lines.append(_md_code_block("\n".join(f"- {p}" for p in issues["noncanonical_links"][:50])))
        if len(issues["noncanonical_links"]) > 50:
            lines.append(f"... and {len(issues['noncanonical_links']) - 50} more")
        lines.append("")
        lines.append(_md_action("Rewrite links to target the canonical file stem, e.g. `[[Page-Name|Page Name]]`."))
        lines.append("")

    if issues["drafts"]:
        lines.append(_md_header("Draft Pages", level=3))
        lines.append(_md_code_block("\n".join(f"- [[{p}]]" for p in issues["drafts"])))
        lines.append("")

    if issues["invalid_status"]:
        lines.append(_md_header("Invalid Status", level=3))
        lines.append(_md_code_block("\n".join(f"- {m}" for m in issues["invalid_status"])))
        lines.append("")
        lines.append(_md_action("Fix the status typo. Lifecycle: seed -> developing -> mature -> evergreen; draft/archived remain valid."))
        lines.append("")

    if issues["lifecycle_mismatch"]:
        lines.append(_md_header("Lifecycle Mismatch (advisory)", level=3))
        lines.append(_md_code_block("\n".join(f"- {m}" for m in issues["lifecycle_mismatch"])))
        lines.append("")
        lines.append(_md_action("Either deepen the page to justify mature/evergreen, or lower its status to developing."))
        lines.append("")

    if issues["claim_issues"]:
        lines.append(_md_header("Claim Issues (advisory)", level=3))
        lines.append(_md_code_block("\n".join(f"- {m}" for m in issues["claim_issues"])))
        lines.append("")
        lines.append(_md_action("Bind every claim to a source declared in the page's own sources/sources_meta, and keep claim statuses within accepted/provisional/contested/unsupported."))
        lines.append("")

    if issues["shallow_pages"]:
        lines.append(_md_header("Shallow Pages (advisory)", level=3))
        shallow_rows: List[List[str]] = []
        for finding in issues["shallow_page_details"]:
            ratio = finding["compression_ratio"]
            compression = "n/a" if ratio is None else f"{ratio:.2%}"
            reasons = ", ".join(
                f"`{_md_table_cell(reason)}`" for reason in finding["reasons"]
            )
            title = _md_table_cell(finding["page_title"])
            stem = _md_table_cell(finding["page_stem"])
            shallow_rows.append(
                [
                    f"[{title}](wiki/{stem}.md)",
                    str(finding["knowledge_chars"]),
                    str(finding["meaningful_paragraphs"]),
                    str(finding["substantive_sections"]),
                    str(finding["source_count"]),
                    f"{finding['local_source_chars']:,}",
                    compression,
                    reasons,
                ]
            )
        lines.append(
            _md_table(
                [
                    "Page",
                    "Knowledge",
                    "Paragraphs",
                    "Sections",
                    "Sources",
                    "Source chars",
                    "Compression",
                    "Reasons",
                ],
                shallow_rows,
                alignments=[
                    "left",
                    "right",
                    "right",
                    "right",
                    "right",
                    "right",
                    "right",
                    "left",
                ],
            )
        )
        lines.append("")
        lines.append(_md_action(
            "Investigate source coverage and missing reasoning; do not pad pages mechanically to satisfy thresholds."
        ))
        lines.append("")

    print("\n".join(lines))
    return 0

def cmd_status(args: argparse.Namespace) -> int:
    """Show wiki status overview."""
    LOG.info("cmd_status")

    from src.llm_wiki.config import load_config
    from src.llm_wiki.core import WikiManager, find_wiki_root

    wiki_root = find_wiki_root(PROJECT_ROOT)
    if not wiki_root:
        print(_md_info("Error: Cannot find wiki root."))
        return 1

    config = load_config(wiki_root)
    wiki = WikiManager(wiki_root / "wiki")
    pages = wiki.list_pages()
    recent_logs = wiki.read_log(5)

    LOG.info("Status: root=%s pages=%d", wiki_root, len(pages))

    lines: List[str] = []
    lines.append(_md_header("Wiki Status"))
    lines.append("")

    # Overview table
    status_counts: Dict[str, int] = {}
    for p in pages:
        s = p.status
        status_counts[s] = status_counts.get(s, 0) + 1

    lines.append(_md_header("Overview", level=3))
    lines.append(_md_table(
        ["Metric", "Value"],
        [
            ["Wiki Root", str(wiki_root)],
            ["Total Pages", str(len(pages))],
            ["Active", str(status_counts.get("active", 0))],
            ["Draft", str(status_counts.get("draft", 0))],
            ["Archived", str(status_counts.get("archived", 0))],
        ],
    ))
    lines.append("")

    # Lifecycle maturity distribution (seed -> developing -> mature -> evergreen)
    from src.llm_wiki.core import LIFECYCLE_STATES
    lines.append(_md_header("Lifecycle", level=3))
    lines.append(_md_table(
        ["Stage", "Pages"],
        [[stage, str(status_counts.get(stage, 0))] for stage in LIFECYCLE_STATES],
    ))
    lines.append("")

    # Embedding status
    emb = config.get("embedding", {})
    lines.append(_md_header("Embedding", level=3))
    lines.append(_md_table(
        ["Setting", "Value"],
        [
            ["Enabled", "Yes" if emb.get("enabled") else "No"],
            ["Provider", str(emb.get("provider", "N/A"))],
            ["Model", str(emb.get("model", "N/A"))],
        ],
    ))
    lines.append("")

    # Recent activity
    if recent_logs:
        lines.append(_md_header("Recent Activity", level=3))
        for entry in recent_logs:
            first_line = entry.strip().split("\n")[0]
            lines.append(f"- {first_line}")
        lines.append("")

    print("\n".join(lines))
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    """
    Semantic query over wiki pages.
    When embedding is enabled, this returns candidate pages via vector search.
    The Agent then reads those pages and synthesizes the final answer with LLM.
    """
    LOG.info("cmd_query: query=%s semantic=%s", args.query_text, args.semantic)

    from src.llm_wiki.config import load_config
    from src.llm_wiki.core import WikiManager, find_wiki_root
    from src.llm_wiki.embeddings import create_provider
    from src.llm_wiki.retrieval import EmbeddingIndex

    wiki_root = find_wiki_root(PROJECT_ROOT)
    if not wiki_root:
        print(_md_info("Error: Cannot find wiki root."))
        return 1

    config = load_config(wiki_root)
    wiki = WikiManager(wiki_root / "wiki")

    lines: List[str] = []
    lines.append(_md_header(f"Query: {args.query_text}"))
    lines.append("")

    emb_cfg = config.get("embedding", {})
    use_semantic = args.semantic or emb_cfg.get("enabled", False)

    if not use_semantic:
        lines.append(_md_info("Semantic search is disabled. Falling back to keyword listing."))
        pages = wiki.list_pages()
        lines.append(f"\nTotal pages: {len(pages)}")
        lines.append(_md_code_block("\n".join(f"- [[{p.title}]] (tags: {', '.join(p.tags)})" for p in pages[:20])))
        lines.append("")
        lines.append(_md_action("Agent: Read `wiki/index.md` to locate relevant topics, then read specific pages."))
        print("\n".join(lines))
        return 0

    # Semantic search path
    LOG.info("Running semantic search...")
    try:
        provider = create_provider(config)
        if not provider:
            LOG.error("Embedding provider returned None")
            print(_md_info("Error: Embedding provider unavailable. Check config.yaml."))
            return 1

        index = EmbeddingIndex(wiki, provider)
        if not index.cache or not index.cache.get("pages"):
            LOG.error("Embedding index empty")
            print(_md_info("Error: Embedding index is empty. Run `python scripts/agent-bridge.py index` first."))
            return 1

        retrieval_cfg = config.get("retrieval", {})
        results = index.search(
            args.query_text,
            top_k=retrieval_cfg.get("top_k", 10),
            keyword_weight=retrieval_cfg.get("keyword_weight", 0.3),
            vector_weight=retrieval_cfg.get("vector_weight", 0.5),
            link_weight=retrieval_cfg.get("link_weight", 0.2),
            enable_link_traversal=retrieval_cfg.get("enable_link_traversal", True),
        )
        LOG.info("Semantic search returned %d results", len(results))

        if not results:
            lines.append("No relevant pages found via semantic search.")
            print("\n".join(lines))
            return 0

        lines.append(_md_header("Semantic Results", level=3))
        rows = []
        for title, score in results:
            rows.append([f"[[{title}]]", f"{score:.3f}"])
        lines.append(_md_table(["Page", "Relevance"], rows))
        lines.append("")
        lines.append(_md_action("Agent: Read the top-ranked pages and synthesize an answer with citations."))

        print("\n".join(lines))
        return 0

    except Exception as e:
        LOG.exception("Semantic search failed")
        print(_md_info(f"Error during semantic search: {e}"))
        return 1


def cmd_merge(args: argparse.Namespace) -> int:
    """Execute a safe merge between two wiki pages with diff preview."""
    LOG.info("cmd_merge: source=%s target=%s strategy=%s dry_run=%s",
             args.source, args.target, args.strategy, args.dry_run)

    from src.llm_wiki.config import load_config
    from src.llm_wiki.core import WikiManager, find_wiki_root
    from src.llm_wiki.merge import ContentMerger, MergeStrategy, SafeWriter

    wiki_root = find_wiki_root(PROJECT_ROOT)
    if not wiki_root:
        print(_md_info("Error: Cannot find wiki root."))
        return 1

    config = load_config(wiki_root)
    wiki = WikiManager(wiki_root / "wiki")

    source_page = wiki.get_page(args.source)
    target_page = wiki.get_page(args.target)

    if not source_page:
        print(_md_info(f"Error: Source page not found: `{args.source}`"))
        return 1
    if not target_page:
        print(_md_info(f"Error: Target page not found: `{args.target}`"))
        return 1

    # Check strategy allowlist
    linking_cfg = config.get("linking", {})
    allowed = linking_cfg.get("deep_mode", {}).get("strategies_allowed", [])
    if args.strategy not in allowed:
        print(_md_info(f"Error: Strategy `{args.strategy}` not allowed. Allowed: {', '.join(allowed)}"))
        return 1

    strategy_enum = MergeStrategy(args.strategy)
    merger = ContentMerger(wiki)
    writer = SafeWriter(wiki)

    context = {
        "target": args.source,
        "relation_desc": f"Linked from [[{args.source}]]",
    }
    if strategy_enum == MergeStrategy.APPEND_SECTION:
        context["section_title"] = "## 最新进展"

    LOG.info("Preparing merge: strategy=%s", args.strategy)
    new_content = merger.merge(target_page, "", strategy_enum, context)
    diff = merger.generate_diff(
        target_page.path.read_text(encoding="utf-8"),
        new_content,
    )

    lines: List[str] = []
    lines.append(_md_header(f"Merge Proposal: {args.source} → {args.target}"))
    lines.append("")
    lines.append(_md_info(f"Strategy: `{args.strategy}` | Target: [[{args.target}]]"))
    lines.append("")

    lines.append(_md_header("Diff", level=3))
    lines.append(_md_code_block(diff, lang="diff"))
    lines.append("")

    if args.dry_run:
        lines.append(_md_action("This is a dry-run. Review the diff above."))
        lines.append(_md_action("To apply, run the same command without `--dry-run`."))
    else:
        proposal = writer.prepare(target_page, new_content,
                                  reason=f"Link {args.source} → {args.target}",
                                  strategy=strategy_enum)
        backup = writer.apply(proposal)
        LOG.info("Merge applied. Backup: %s", backup)
        lines.append(_md_info(f"Merge applied successfully."))
        lines.append(f"- Backup: `{backup}`")
        lines.append(_md_action("To rollback: check `wiki/.backups/` for the latest backup."))

    print("\n".join(lines))
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    """Build or update the embedding index."""
    LOG.info("cmd_index: force=%s", args.force)

    from src.llm_wiki.config import load_config
    from src.llm_wiki.core import WikiManager, find_wiki_root
    from src.llm_wiki.embeddings import create_provider
    from src.llm_wiki.retrieval import EmbeddingIndex

    wiki_root = find_wiki_root(PROJECT_ROOT)
    if not wiki_root:
        print(_md_info("Error: Cannot find wiki root."))
        return 1

    config = load_config(wiki_root)
    emb_cfg = config.get("embedding", {})
    if not emb_cfg.get("enabled", False):
        print(_md_info("Error: Embedding is disabled in config.yaml. Set `embedding.enabled: true`."))
        return 1

    try:
        provider = create_provider(config)
        if not provider:
            print(_md_info("Error: Cannot create embedding provider. Check config.yaml."))
            return 1

        wiki = WikiManager(wiki_root / "wiki")
        idx = EmbeddingIndex(wiki, provider)
        LOG.info("Building embedding index (force=%s)...", args.force)
        indexed, skipped = idx.build(force=args.force)
        LOG.info("Index complete: indexed=%d skipped=%d", indexed, skipped)

        lines: List[str] = []
        lines.append(_md_header("Embedding Index Update"))
        lines.append("")
        lines.append(_md_table(
            ["Metric", "Value"],
            [
                ["Provider", provider.name],
                ["Indexed / Updated", str(indexed)],
                ["Skipped (unchanged)", str(skipped)],
            ],
        ))
        lines.append("")
        print("\n".join(lines))
        return 0

    except Exception as e:
        LOG.exception("Index build failed")
        print(_md_info(f"Error: {e}"))
        return 1


def cmd_zotero_plan(args: argparse.Namespace) -> int:
    """Build a read-only Zotero metadata and managed-tag synchronization plan."""
    LOG.info("cmd_zotero_plan: snapshot=%s item_keys=%s", args.snapshot, args.item_keys)

    from src.llm_wiki.core import WikiManager, find_wiki_root
    from src.llm_wiki.zotero_plan import (
        build_zotero_plan,
        collect_zotero_bindings,
        load_snapshot,
        plan_to_manifest,
    )

    wiki_root = find_wiki_root(PROJECT_ROOT)
    if not wiki_root:
        print(_md_info("Error: Cannot find wiki root."))
        return 1

    wiki = WikiManager(wiki_root / "wiki")
    bindings = collect_zotero_bindings(wiki)
    selected_keys = set(args.item_keys or []) or None

    library_id = ""
    collection_name = ""
    collection_key = ""
    snapshot_items = None
    if args.snapshot:
        snapshot_path = Path(args.snapshot)
        if not snapshot_path.is_absolute():
            snapshot_path = wiki_root / snapshot_path
        if not snapshot_path.exists():
            print(_md_info(f"Error: Snapshot not found: {snapshot_path}"))
            return 1
        try:
            library_id, collection_name, collection_key, snapshot_items = load_snapshot(snapshot_path)
        except (OSError, ValueError, TypeError) as exc:
            LOG.error("Cannot load Zotero snapshot: %s", exc)
            print(_md_info(f"Error: Cannot load Zotero snapshot: {exc}"))
            return 1

    plan = build_zotero_plan(
        bindings,
        snapshot_items,
        library_id=library_id,
        collection_name=collection_name,
        collection_key=collection_key,
        item_keys=selected_keys,
    )

    if not plan.items:
        print(_md_info("No Zotero items matched the requested scope."))
        return 0

    bound_count = sum(bool(item.wiki_pages) for item in plan.items)
    add_tag_count = sum(bool(item.add_tags) for item in plan.items)
    remove_tag_count = sum(bool(item.remove_candidates) for item in plan.items)
    relation_count = sum(bool(item.relation_candidates) for item in plan.items)
    doi_counts: Dict[str, int] = {}
    for item in plan.items:
        doi_counts[item.doi_state] = doi_counts.get(item.doi_state, 0) + 1

    lines: List[str] = []
    title = "Zotero Sync Plan"
    if plan.collection_name:
        title += f": {plan.collection_name}"
    lines.append(_md_header(title))
    lines.append("")
    lines.append(_md_info(
        "Read-only plan. This command does not connect to Zotero and does not mutate Zotero or wiki files."
    ))
    lines.append("")
    lines.append(_md_header("Scope", level=3))
    lines.append(_md_table(
        ["Field", "Value"],
        [
            ["Library ID", plan.library_id or "Not provided"],
            ["Collection", plan.collection_name or "Wiki bindings only"],
            ["Collection Key", plan.collection_key or "Not provided"],
            ["Items", str(len(plan.items))],
            ["Wiki-bound Items", str(bound_count)],
            ["Items with Tag Additions", str(add_tag_count)],
            ["Items with Removal Candidates", str(remove_tag_count)],
            ["Items with Relation Candidates", str(relation_count)],
        ],
    ))
    lines.append("")

    lines.append(_md_header("DOI Audit", level=3))
    lines.append(_md_table(
        ["State", "Count"],
        [[state, str(count)] for state, count in sorted(doi_counts.items())],
    ))
    lines.append("")

    lines.append(_md_header("Items", level=3))
    rows = []
    for item in plan.items:
        title_text = item.title if len(item.title) <= 64 else f"{item.title[:61]}..."
        rows.append([
            item.item_key,
            title_text,
            ", ".join(item.wiki_pages) or "—",
            item.doi_state,
            ", ".join(sorted(item.add_tags)) or "—",
            ", ".join(sorted(item.remove_candidates)) or "—",
            ", ".join(item.relation_candidates) or "—",
            "; ".join(item.actions) or "none",
        ])
    lines.append(_md_table(
        ["Item Key", "Title", "Wiki Pages", "DOI", "Add Tags", "Review Removals", "Relation Candidates", "Actions"],
        rows,
    ))
    lines.append("")

    if plan.warnings:
        lines.append(_md_header("Warnings", level=3))
        lines.extend(f"- {warning}" for warning in plan.warnings)
        lines.append("")

    lines.append(_md_header("Actionable Items", level=3))
    lines.append(_md_action(
        "Agent: verify DOI candidates and publication identities through approved external metadata sources, "
        "then use Zotero MCP incremental writes only after reviewing this plan."
    ))
    lines.append(_md_action(
        "Agent: do not remove user-managed tags; collection-equivalent tags are review candidates, not automatic mutations."
    ))
    lines.append("")

    if args.manifest_out:
        manifest_path = Path(args.manifest_out)
        if manifest_path.is_absolute():
            resolved_manifest = manifest_path.resolve()
        else:
            resolved_manifest = (wiki_root / manifest_path).resolve()
        allowed_root = (wiki_root / "temp").resolve()
        if resolved_manifest != allowed_root and allowed_root not in resolved_manifest.parents:
            print(_md_info("Error: --manifest-out must stay under the project temp/ directory."))
            return 1
        resolved_manifest.parent.mkdir(parents=True, exist_ok=True)
        import yaml
        resolved_manifest.write_text(
            yaml.safe_dump(plan_to_manifest(plan), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        lines.append(_md_info(f"Review manifest written to: {resolved_manifest}"))
        lines.append("")

    print("\n".join(lines))
    return 0


def cmd_zotero_refresh(args: argparse.Namespace) -> int:
    """Run one-shot DOI, citation, and publication freshness checks."""
    import asyncio

    import yaml

    from src.llm_wiki.config import load_config
    from src.llm_wiki.core import find_wiki_root
    from src.llm_wiki.zotero_refresh import (
        report_to_manifest,
        run_live_refresh,
        settings_from_config,
    )

    wiki_root = find_wiki_root(PROJECT_ROOT)
    if not wiki_root:
        print(_md_info("Error: Cannot find wiki root."))
        return 1

    config = load_config(wiki_root)
    enrichment_config = config.get("zotero_enrichment") or {}
    settings = settings_from_config(config)

    cache_path = Path(str(enrichment_config.get("cache_path") or "var/zotero-enrichment.sqlite"))
    if not cache_path.is_absolute():
        cache_path = wiki_root / cache_path
    cache_path = cache_path.resolve()
    allowed_cache_root = (wiki_root / "var").resolve()
    if cache_path != allowed_cache_root and allowed_cache_root not in cache_path.parents:
        print(_md_info("Error: Zotero enrichment cache must stay under the project var/ directory."))
        return 1

    mcp_config_path = Path(args.mcp_config or ".mcp.json")
    if not mcp_config_path.is_absolute():
        mcp_config_path = wiki_root / mcp_config_path
    if not mcp_config_path.exists():
        print(_md_info(f"Error: MCP config not found: {mcp_config_path}"))
        return 1

    try:
        report = asyncio.run(
            run_live_refresh(
                wiki_root,
                collection_key=args.collection_key,
                settings=settings,
                cache_path=cache_path,
                mcp_config_path=mcp_config_path,
                mcp_server_name=args.mcp_server,
                item_keys=set(args.item_keys or []) or None,
                limit=args.limit,
                force=args.force,
                apply_safe=args.apply_safe,
            )
        )
    except Exception as exc:
        LOG.exception("Zotero refresh failed")
        print(_md_info(f"Error: Zotero refresh failed: {exc}"))
        return 1

    manifest_path = None
    if args.manifest_out:
        manifest_path = Path(args.manifest_out)
        if not manifest_path.is_absolute():
            manifest_path = wiki_root / manifest_path
        manifest_path = manifest_path.resolve()
        allowed_manifest_root = (wiki_root / "temp").resolve()
        if manifest_path != allowed_manifest_root and allowed_manifest_root not in manifest_path.parents:
            print(_md_info("Error: --manifest-out must stay under the project temp/ directory."))
            return 1
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            yaml.safe_dump(report_to_manifest(report), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    status_counts: Dict[str, int] = {}
    for item in report.items:
        status_counts[item.doi_status] = status_counts.get(item.doi_status, 0) + 1
    safe_count = sum(item.has_safe_changes for item in report.items)
    review_count = sum(bool(item.metadata_review) for item in report.items)
    error_count = sum(bool(item.errors) for item in report.items)

    lines: List[str] = []
    lines.append(_md_header(f"Zotero Refresh: {report.collection_name}"))
    lines.append("")
    mode = "Applied safe updates through Zotero MCP with write-back verification." if args.apply_safe else "Dry-run only. No Zotero fields or tags were modified."
    lines.append(_md_info(mode))
    lines.append("")
    lines.append(_md_header("Summary", level=3))
    lines.append(_md_table(
        ["Metric", "Value"],
        [
            ["Collection Key", report.collection_key],
            ["Items", str(len(report.items))],
            ["Items with Safe Updates", str(safe_count)],
            ["Items Requiring Review", str(review_count)],
            ["Items with Errors", str(error_count)],
            ["Items Applied", str(report.applied_count)],
            ["Cache", str(cache_path)],
        ],
    ))
    lines.append("")
    lines.append(_md_header("DOI Status", level=3))
    lines.append(_md_table(
        ["Status", "Count"],
        [[key, str(value)] for key, value in sorted(status_counts.items())],
    ))
    lines.append("")
    lines.append(_md_header("Items", level=3))
    rows = []
    for item in report.items:
        title = item.title if len(item.title) <= 54 else f"{item.title[:51]}..."
        safe_parts = []
        if item.safe_set_keys:
            safe_parts.append(f"Extra:{len(item.safe_set_keys)}")
        if item.add_tags:
            safe_parts.append(f"+tags:{len(item.add_tags)}")
        if item.remove_tags:
            safe_parts.append(f"-tags:{len(item.remove_tags)}")
        if item.safe_fields:
            safe_parts.append(f"fields:{len(item.safe_fields)}")
        rows.append([
            item.item_key,
            title,
            item.doi_status,
            f"{item.citation_provider}:{item.citation_count}" if item.citation_provider else "—",
            ", ".join(safe_parts) or "—",
            ", ".join(item.metadata_review) or "—",
            "; ".join(item.errors) or "—",
        ])
    lines.append(_md_table(
        ["Item", "Title", "DOI", "Citations", "Safe Updates", "Review", "Errors"],
        rows,
    ))
    lines.append("")
    if manifest_path:
        lines.append(_md_info(f"Review manifest written to: {manifest_path}"))
        lines.append("")
    if review_count:
        lines.append(_md_action("Agent: review DOI and published-version candidates before changing bibliographic identity."))
    if not args.apply_safe and safe_count:
        lines.append(_md_action("Agent: re-run with --apply-safe only after reviewing the safe update set."))
    lines.append("")
    print("\n".join(lines))
    apply_failed = any(
        any(error.startswith("safe apply failed:") for error in item.errors)
        for item in report.items
    )
    return 1 if args.apply_safe and apply_failed else 0


def cmd_capabilities(args: argparse.Namespace) -> int:
    """Print the effective capability contracts (defaults + config overrides)."""
    LOG.info("cmd_capabilities")

    from src.llm_wiki.capabilities import CAPABILITIES, CapabilityError, get_capability
    from src.llm_wiki.config import load_config
    from src.llm_wiki.core import find_wiki_root

    config: Dict[str, Any] = {}
    wiki_root = find_wiki_root(PROJECT_ROOT)
    if wiki_root:
        try:
            config = load_config(wiki_root)
        except ValueError as exc:
            print(_md_info(f"Error: {exc}"))
            return 1

    rows: List[List[str]] = []
    try:
        for name, declared in CAPABILITIES.items():
            cap = get_capability(name, config)
            overridden = " (config)" if cap != declared else ""
            rows.append([
                name,
                "yes" if cap.enabled else "**disabled**",
                _md_table_cell(", ".join(cap.write_scope) or "—") + overridden,
                "yes" if cap.network else "no",
                "yes" if cap.dry_run else "no",
            ])
    except CapabilityError as exc:
        print(_md_info(f"Error: {exc}"))
        return 1

    lines: List[str] = [_md_header("Capability Contracts"), ""]
    lines.append(_md_table(["Command", "Enabled", "Write Scope", "Network", "Dry-Run"], rows))
    lines.append("")
    lines.append(_md_info(
        "Defaults are declared in code. `capabilities:` in config.yaml may only "
        "tighten a contract (disable a command, narrow its write scope); "
        "widening attempts are rejected."
    ))
    print("\n".join(lines))
    return 0


def cmd_hot(args: argparse.Namespace) -> int:
    """Print wiki/hot.md - bounded recent-activity context for session resume."""
    LOG.info("cmd_hot")

    from src.llm_wiki.core import find_wiki_root

    wiki_root = find_wiki_root(PROJECT_ROOT)
    if not wiki_root:
        print(_md_info("Error: Cannot find wiki root."))
        return 1

    hot_file = wiki_root / "wiki" / "hot.md"
    if not hot_file.exists():
        print(_md_info("No recorded activity yet (wiki/hot.md does not exist). "
                       "It is maintained automatically by apply-bundle."))
        return 0

    print(hot_file.read_text(encoding="utf-8").rstrip())
    return 0


def cmd_apply_bundle(args: argparse.Namespace) -> int:
    """Apply a transaction bundle: atomic multi-file writes with dry-run preview."""
    LOG.info("cmd_apply_bundle: manifest=%s dry_run=%s", args.manifest, args.dry_run)

    from src.llm_wiki.core import find_wiki_root
    from src.llm_wiki.transaction import TransactionError, load_bundle

    wiki_root = find_wiki_root(PROJECT_ROOT)
    if not wiki_root:
        print(_md_info("Error: Cannot find wiki root."))
        return 1

    manifest = Path(args.manifest)
    if not manifest.exists():
        print(_md_info(f"Error: Manifest not found: `{manifest}`"))
        return 1

    try:
        tx = load_bundle(manifest, wiki_root)
    except TransactionError as exc:
        print(_md_info(f"Error: {exc}"))
        return 1

    from src.llm_wiki.capabilities import CapabilityError, check_write_paths
    from src.llm_wiki.config import load_config

    try:
        check_write_paths("apply-bundle", [op.path for op in tx.ops], load_config(wiki_root))
    except CapabilityError as exc:
        print(_md_info(f"Error: {exc}"))
        return 1

    if args.dry_run:
        checks = tx.check()
        lines: List[str] = [_md_header("Transaction Preview"), ""]
        rows = [
            [c.op.op, str(c.op.path), "ok" if c.ok else "FAIL", _md_table_cell(c.detail)]
            for c in checks
        ]
        lines.append(_md_table(["Op", "Path", "Status", "Detail"], rows))
        lines.append("")
        lines.append(_md_header("Diff", level=3))
        lines.append(_md_code_block(tx.diff(), "diff"))
        lines.append("")
        lines.append(_md_action(
            "Review the diff. Fill any missing `expected_sha256` values shown above "
            "into the manifest, then re-run without `--dry-run` to apply."
        ))
        print("\n".join(lines))
        return 0 if all(c.ok for c in checks) else 1

    try:
        receipt = tx.apply()
    except TransactionError as exc:
        print(_md_info(f"Error: {exc}"))
        return 1

    from src.llm_wiki.core import WikiManager
    WikiManager(wiki_root / "wiki").record_activity(
        f"apply-bundle {receipt.tx_id}", receipt.changed
    )

    lines = [_md_header("Transaction Applied"), ""]
    lines.append(f"- **Operation ID**: `{receipt.tx_id}`")
    lines.append(f"- **Journal**: `{receipt.journal_dir}`")
    lines.append("- **Changed paths**:")
    for changed in receipt.changed:
        lines.append(f"  - `{changed}`")
    print("\n".join(lines))
    return 0


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agent-bridge",
        description="Unified Agent entry point for llm-wiki operations.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # check
    subparsers.add_parser("check", help="Check environment and wiki status")

    # link
    link_parser = subparsers.add_parser("link", help="Discover relations for a page")
    link_parser.add_argument("--source", required=True, help="Source page title")
    link_parser.add_argument("--mode", choices=["light", "deep"], default=None)
    link_parser.add_argument("--max-related", type=int, default=5)

    # relink
    relink_parser = subparsers.add_parser("relink", help="Batch global relation discovery")
    relink_parser.add_argument("--since", help="Date cutoff (YYYY-MM-DD)")
    relink_parser.add_argument("--mode", choices=["light", "deep"], default="deep")
    relink_parser.add_argument("--dry-run", action="store_true")

    # lint
    subparsers.add_parser("lint", help="Check wiki health")

    # status
    subparsers.add_parser("status", help="Show wiki overview")

    # query
    query_parser = subparsers.add_parser("query", help="Semantic query (when embedding enabled)")
    query_parser.add_argument("query_text", help="Query string")
    query_parser.add_argument("--semantic", action="store_true", help="Force semantic search")

    # merge
    merge_parser = subparsers.add_parser("merge", help="Safely merge content between pages")
    merge_parser.add_argument("--source", required=True)
    merge_parser.add_argument("--target", required=True)
    merge_parser.add_argument("--strategy", required=True,
                              choices=["link_only", "append_related", "append_section", "update_concept"])
    merge_parser.add_argument("--dry-run", action="store_true")

    # index
    index_parser = subparsers.add_parser("index", help="Build/update embedding index")
    index_parser.add_argument("--force", action="store_true", help="Force rebuild all")

    # apply-bundle
    bundle_parser = subparsers.add_parser(
        "apply-bundle",
        help="Apply a transaction bundle (atomic multi-file writes)",
    )
    bundle_parser.add_argument("manifest", help="Path to the transaction bundle YAML manifest")
    bundle_parser.add_argument("--dry-run", action="store_true",
                               help="Preview checks and diff without writing")

    # capabilities
    subparsers.add_parser("capabilities", help="Show effective capability contracts")

    # hot
    subparsers.add_parser("hot", help="Print bounded recent-activity context (wiki/hot.md)")

    # zotero-plan
    zotero_parser = subparsers.add_parser(
        "zotero-plan",
        help="Build a read-only Zotero metadata/tag synchronization plan",
    )
    zotero_parser.add_argument(
        "--snapshot",
        help="MCP-produced Zotero collection snapshot in YAML or JSON",
    )
    zotero_parser.add_argument(
        "--item-key",
        dest="item_keys",
        action="append",
        help="Restrict the plan to a Zotero item key (repeatable)",
    )
    zotero_parser.add_argument(
        "--manifest-out",
        help="Write a review-only YAML mutation manifest under temp/",
    )

    # zotero-refresh
    refresh_parser = subparsers.add_parser(
        "zotero-refresh",
        help="Refresh DOI, citation, journal, and preprint publication state through Zotero MCP",
    )
    refresh_parser.add_argument("--collection-key", required=True, help="Zotero collection key")
    refresh_parser.add_argument(
        "--item-key",
        dest="item_keys",
        action="append",
        help="Restrict refresh to an item key (repeatable)",
    )
    refresh_parser.add_argument("--limit", type=int, help="Limit items for a smoke test")
    refresh_parser.add_argument("--force", action="store_true", help="Ignore freshness timestamps and cache age")
    refresh_parser.add_argument(
        "--apply-safe",
        action="store_true",
        help="Apply only Extra, llm-wiki status tag, and safe URL updates through MCP",
    )
    refresh_parser.add_argument(
        "--manifest-out",
        help="Write a review-only refresh manifest under temp/",
    )
    refresh_parser.add_argument(
        "--mcp-config",
        default=".mcp.json",
        help="MCP configuration file (default: .mcp.json)",
    )
    refresh_parser.add_argument(
        "--mcp-server",
        default="zotero",
        help="Configured MCP server name (default: zotero)",
    )

    args = parser.parse_args(argv)

    LOG.info("Agent Bridge invoked: command=%s args=%s", args.command, vars(args))

    dispatch = {
        "check": cmd_check,
        "link": cmd_link,
        "relink": cmd_relink,
        "lint": cmd_lint,
        "status": cmd_status,
        "query": cmd_query,
        "merge": cmd_merge,
        "index": cmd_index,
        "apply-bundle": cmd_apply_bundle,
        "capabilities": cmd_capabilities,
        "hot": cmd_hot,
        "zotero-plan": cmd_zotero_plan,
        "zotero-refresh": cmd_zotero_refresh,
    }

    handler = dispatch.get(args.command)
    if not handler:
        parser.print_help()
        return 1

    # Capability gate: config.yaml may disable commands (fail closed).
    # If the config cannot be loaded here, the command's own setup reports it.
    if args.command != "capabilities":
        try:
            from src.llm_wiki.capabilities import CapabilityError, check_enabled
            from src.llm_wiki.config import load_config
            from src.llm_wiki.core import find_wiki_root

            gate_root = find_wiki_root(PROJECT_ROOT)
            if gate_root:
                check_enabled(args.command, load_config(gate_root))
        except CapabilityError as exc:
            print(_md_info(f"Error: {exc}"))
            return 1
        except Exception as exc:
            LOG.debug("capability gate skipped: %s", exc)

    return handler(args)


if __name__ == "__main__":
    # Ensure UTF-8 output on Windows terminals
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
