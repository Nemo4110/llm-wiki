---
name: llm-wiki
version: "1.5.2"
description: "Use when an AI Agent (Claude Code, Codex, OpenClaw, or similar) needs to operate an llm-wiki knowledge base: ingest source files into Markdown wiki pages, answer questions from wiki/index.md and linked pages, run agent-bridge status/lint/link/relink/merge/query/index tasks, preserve provenance and temporal metadata, or use Zotero as a literature-discovery layer."
---

# LLM-Wiki

## Core Principle

Treat the LLM as the programmer and the wiki as the codebase. The user provides materials and judgment; the Agent extracts durable knowledge, preserves provenance, maintains links, and keeps the Markdown wiki structurally consistent.

Keep this file as the operational skill. Use `README.md` for user-facing overview, `AGENTS.md` / `CLAUDE.md` for the full protocol, and `ROADMAP.md` for project plans.

## Start Every Wiki Task

1. Read `AGENTS.md` or `CLAUDE.md` when the task touches wiki behavior, source handling, or ingest/query protocol.
2. Use the project Python: `.venv\Scripts\python.exe` on Windows, `.venv/bin/python` on Unix, or `uv run python` when configured.
3. Run `<PY> scripts/agent-bridge.py check` before wiki operations. If it reports missing dependencies, state the exact blocker and continue only with tasks that do not require the unavailable runtime.
4. Protect `sources/`: never write Agent-generated summaries, drafts, or speculative content there. Only user-provided files or verified network/Zotero fetches may be source assets.
5. Check `git status --short` before editing. Do not revert user changes.

## Choose the Work Mode

| Task | Use | Notes |
| --- | --- | --- |
| Status, lint, link discovery, relink, merge, semantic query, embedding index | `scripts/agent-bridge.py` | Algorithmic tasks. Prefer dry-run before writing. |
| Ingest source material | Protocol mode | Requires LLM judgment: read source, extract metadata, create/update pages. |
| Answer wiki questions | Protocol mode | Read `wiki/index.md`, relevant pages, and link neighbors; synthesize with `[[PageName]]` citations. |
| Apply relation updates | Hybrid | Let `agent-bridge.py` discover candidates, then review and merge only safe changes. |

Agent Bridge quick commands:

```bash
<PY> scripts/agent-bridge.py check
<PY> scripts/agent-bridge.py status
<PY> scripts/agent-bridge.py lint
<PY> scripts/agent-bridge.py link --source "PageName" --mode light
<PY> scripts/agent-bridge.py merge --source "NewPage" --target "OldPage" --strategy append_related --dry-run
<PY> scripts/agent-bridge.py relink --since 2026-04-20 --mode deep --dry-run
<PY> scripts/agent-bridge.py index
<PY> scripts/agent-bridge.py query "question" --semantic
```

Use legacy `python -m src.llm_wiki ...` only for human scripting or debugging. Do not use the legacy CLI as a substitute for LLM judgment during ingest.

### Interpret depth lint correctly

`agent-bridge.py lint` reports `Shallow Pages` as warning-only findings. The detector excludes related-page, source, and changelog sections, then combines normalized knowledge size, paragraph and section structure, local text-source volume, source count, and compression ratio. `QRF` is skipped by default; `lint_depth: skip` is reserved for deliberately concise pages whose source-coverage audit explains the exemption.

A clean depth result is not proof of source coverage. Re-read allocated sources and account for important mechanisms, equations, evidence, comparisons, procedures, failure modes, trade-offs, and decision rules. Never pad a page mechanically to satisfy a threshold.

## Ingest Workflow

1. Verify every source and extraction path before interpreting it.
2. Build a temporary source content map before drafting. Record major topic units, mechanisms, equations, quantitative evidence, comparisons, procedures, failure modes, decision rules, open questions, and extraction uncertainty.
3. Allocate each important unit deliberately: include it in the target page, merge it into an existing page, create a separately reusable concept page, or record a concrete omission reason. Do not omit material merely to fit a summary template.
4. Choose a page archetype and headings from the knowledge shape. The definition, provenance, related pages, sources, and changelog are invariants; mechanism, derivation, comparison, data flow, decision guide, failure modes, evidence, disputes, and open questions are conditional sections.
5. Compose the smallest page that preserves the source-defining reasoning. Explain why, how, under what assumptions, and where a claim fails. Preserve central formulas, numerical context, version differences, and engineering trade-offs when the source depends on them.
6. Run a coverage review before marking the page active. Every important source unit must be present, allocated elsewhere, or intentionally omitted with a reason in working notes.
7. Run a depth review: reject pages that merely restate an abstract, replace causal mechanisms with labels, list comparisons without dimensions, or use generic boundary statements.
8. When ingesting a batch, compare the drafts for template collapse. Similar heading and bullet patterns are acceptable only when the underlying knowledge structure is genuinely similar.
9. Add temporal metadata and visible time anchors where historical order matters.
10. Run link discovery and safe backward merges only after content review passes, then update `wiki/index.md` and `log.md`.

Source maps and coverage notes are temporary Agent working state. Keep them outside `sources/`; retain them under `temp/` only when the user requests an ingest audit or experiment.

Never treat `created` or `updated` as publication dates. They are wiki maintenance dates only.

## Query Workflow

1. Read `wiki/index.md` first.
2. Read relevant pages and their link neighbors. Semantic query may discover candidates, but page content is the source of truth.
3. Answer with citations to wiki pages using `[[PageName]]`.
4. If the answer creates reusable synthesis, ask or decide whether to archive it into the wiki according to user intent.

## Linking Rules

- Link the first meaningful mention of a concept in a local section.
- Keep every internal link resolvable to a real `wiki/*.md` stem by the end of ingest.
- Use canonical file stems and aliases, e.g. `[[AI-Coding-Workflow|AI Coding Workflow]]`.
- Avoid over-linking. Prefer one useful link over repeated noise.
- Describe temporal relationships when useful: early work, follow-up, contemporary route, survey, retrospective, or outdated-but-historically-important.

## Zotero Workflow

Use Zotero as the literature layer and llm-wiki as the distilled Markdown knowledge layer. A recommended public Zotero skill source is:

<https://github.com/openai/plugins/tree/main/plugins/zotero/skills/zotero>

When an Agent has that skill, or an equivalent Zotero-capable skill, it can search the local Zotero library, list collections/tags, export BibTeX/citations, read attachment paths or indexed full text on request, and import BibTeX/RIS records after confirmation.

Before any Zotero operation, verify a Zotero-capable MCP/tool is available and can access the target library. For read workflows, confirm collection search, item metadata, and attachment path/fulltext access work. For write workflows, confirm the exact capability is supported before acting: child note create/update, incremental tag update, and related-item linking are separate gates. If Zotero Desktop, MCP access, or write capability is unavailable, report the blocker and continue only with wiki-local work.

For llm-wiki, Zotero results are source discovery and provenance. Preserve Zotero identifiers in frontmatter when available:

```yaml
sources_meta:
  - title: "Paper Title"
    type: "academic_paper"
    published: "2025-02"
    collected: "2026-05-24"
    ingested: "2026-05-24"
    date_precision: "month"
    zotero_item_key: "ABCD1234"
    citation_key: "author2025title"
    library_id: "0"
    zotero_uri: "zotero://select/items/ABCD1234"
```

Do not build a native llm-wiki Zotero client unless repeated manual workflows prove the need. Arbitrary document upload or attachment management is not part of the verified llm-wiki workflow.

### Zotero-Linked Sources

Use Zotero item keys and attachment keys as cross-device stable identifiers. Store private Zotero source bindings in `sources/zotero/metadata.yaml`; this file is user-local/private and must not be committed. Treat `sources/zotero/` as a generated local symlink cache. Agents may use `scripts/zotero_sources.py --dry-run` to preview and `scripts/zotero_sources.py` to materialize aliases declared in that metadata.

`sources/zotero/metadata.yaml` may contain local absolute paths because it is private operational metadata, not shared wiki content. Do not write LLM-generated summaries, drafts, or synthesized knowledge into `sources/zotero/` or its metadata. Keep generated knowledge in `wiki/`.

For Zotero-backed ingest:

1. Use Zotero MCP to find the collection/item/attachment keys and local attachment paths.
2. Record source bindings in `sources/zotero/metadata.yaml`.
3. Materialize `sources/zotero/...` symlinks with `scripts/zotero_sources.py`.
4. Ingest through normal Protocol mode from the symlink alias path.
5. Preserve `zotero_item_key`, `zotero_attachment_key`, `library_id`, and `zotero_uri` in page frontmatter when available.
6. Create or update Zotero child notes only as index cards: wiki page path, short summary, sync hash/time, and reviewed relation notes. Do not mirror full wiki pages into Zotero notes.
7. After relation review, optionally use Zotero MCP to add `llm-wiki:*` / `rel:*` tags and related-item links.

## Source Fetch Safety

After any network fetch, verify before ingest:

- File is readable and non-empty.
- Content is not an error page, login wall, paywall notice, or JavaScript placeholder.
- Format matches extension, e.g. PDF begins with `%PDF`.
- Title and identifiers match the requested source.
- DOI, arXiv ID, author names, or URL match when provided.

If verification fails, do not create source-derived wiki pages. Record the failure in `log.md` when appropriate and ask the user for a correct source.

## File Handling

- Text and Markdown: read directly.
- PDF: use project Python with PyMuPDF or `scripts/read_pdf.py`; fall back to OCR only when necessary.
- Images: use visual inspection tools when needed.
- Office files and other binaries: use the relevant parser/tooling before extracting knowledge.

Prefer the project-managed Python environment: `.venv`, `uv run`, or the configured conda environment. Do not use global `pip` casually.

## Verification Before Finishing

For documentation-only edits, run:

```bash
git diff --check -- <changed-files>
```

For wiki/runtime operations, also run the relevant `agent-bridge.py` command (`check`, `lint`, `link`, `merge --dry-run`, `status`, or `query`) and report exact blockers if dependencies are missing.

For code changes, run the focused pytest target or the full suite when the change touches shared behavior:

```bash
.venv\Scripts\python.exe -m pytest tests/
```

End by summarizing changed files, verification output, and any skipped checks with the reason.
