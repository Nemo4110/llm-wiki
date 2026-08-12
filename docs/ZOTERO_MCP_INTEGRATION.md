# Zotero MCP Operating Protocol

> Canonical Agent instructions for every Zotero operation in llm-wiki.
>
> **Required integration:** [`54yyyu/zotero-mcp`](https://github.com/54yyyu/zotero-mcp)

## Scope and Authority

Zotero is the literature layer; llm-wiki is the distilled Markdown knowledge layer. Zotero owns bibliographic metadata, attachments, annotations, collections, tags, citation keys, and other library state. llm-wiki owns reusable concepts, cross-source synthesis, wiki links, temporal interpretation, and indexes.

This document is the single operational source of truth for Zotero work. `SKILL.md`, `AGENTS.md`, and the README files should state the integration boundary and point here instead of duplicating workflows.

## Required Tool Boundary

All Zotero operations performed by this skill **MUST go through the MCP tools exposed by [`54yyyu/zotero-mcp`](https://github.com/54yyyu/zotero-mcp)**.

Agents must not substitute:

- another Zotero skill or MCP server;
- a native llm-wiki Zotero client;
- direct Zotero SQLite access;
- direct Zotero Web API calls;
- ad hoc scripts that bypass `zotero-mcp`.

The `zotero-mcp` CLI may be used for installation, setup, diagnostics, and index maintenance. Library reads and writes must use the connected MCP tool surface. Installing, updating, or reconfiguring `zotero-mcp` requires user confirmation under the normal dependency and external-service rules.

## Availability and Capability Gate

Before every Zotero task:

1. Verify that the connected MCP server is `54yyyu/zotero-mcp` and that its Zotero tools are exposed in the current Agent session.
2. Verify access to the intended Zotero library. Discover libraries before switching; do not guess a library ID or type.
3. For read-only work, verify the specific path needed by the task, such as collection search, item metadata, annotations, attachment paths, or full text.
4. For write work, verify the exact write tool and authorization before changing anything. Note creation/update, incremental tag updates, item metadata changes, collection membership changes, attachment uploads, annotations, and related-item operations are separate capability gates.
5. Use only capabilities actually exposed by the installed `zotero-mcp` version. Do not infer a tool exists from an old document or example.

If `zotero-mcp` is missing, unreachable, unauthorized, connected to the wrong library, or lacks the required tool:

- stop the Zotero-side operation;
- state the exact blocker and failed capability gate;
- do not fall back to another Zotero integration or direct API/database access;
- continue only with useful wiki-local work that does not require Zotero access.

## Setup Reference

The upstream project currently supports local, web, and hybrid access modes. Follow its current setup documentation rather than copying environment-specific configuration into llm-wiki.

Typical upstream setup commands are:

```bash
uv tool install zotero-mcp-server
zotero-mcp setup
```

Local read workflows require Zotero Desktop with its local API enabled. Write workflows generally require Zotero Web API credentials or another write-capable mode supported by the connected server. Never print, commit, or copy Zotero API keys or other credentials into project files.

## Tool Selection

Prefer the narrowest exposed MCP tool that satisfies the request:

- **Discovery:** item search, advanced field search, tag search, recent items, or semantic search.
- **Library navigation:** list/switch libraries, search collections, list collection items, and list tags.
- **Metadata and citations:** item metadata, citation-key lookup, and Zotero-rendered bibliography/BibTeX export.
- **Content reading:** item children, attachment paths, PDF outline, selected PDF pages, annotations, notes, and full text.
- **Writes:** add items, update item metadata, incrementally update tags, change collection membership, manage notes, attach files, and create/update annotations.
- **Semantic index:** inspect database status before semantic search; refresh it after adding or materially changing indexed items.

Use metadata and targeted reads before full-text extraction. Full text is resource-intensive and should be read only when the user requests paper-level analysis or metadata, abstracts, annotations, outlines, and selected pages are insufficient.

## Read Workflows

### Find and Inspect One Item

1. Resolve the target by Zotero item key, Better BibTeX citation key, DOI, title/creator/year, or another stable identifier.
2. Read item metadata first.
3. Inspect child attachments and notes when needed.
4. Prefer annotations, PDF outline, and selected page ranges before requesting the entire attachment text.
5. Confirm that title, creators, DOI/arXiv ID, and attachment identity match the requested source before ingest.

### Explore a Collection, Tag, or Topic

1. Discover the active library and resolve the collection or tag without guessing identifiers.
2. Produce a candidate list containing title, creators, date, item type, Zotero item key, and citation key when available.
3. Use semantic search only as candidate discovery and only when its database is ready.
4. Select relevant items before reading full text; do not bulk-read an entire collection by default.
5. For batch ingest, group sources by reusable topic, mechanism, or historical phase instead of mechanically creating one wiki page per Zotero item.

### Query Across Wiki and Zotero

1. Search `wiki/index.md` and relevant wiki pages first for already distilled knowledge.
2. Use Zotero MCP when the question requires source coverage, recent library additions, a specific paper, annotations, notes, or missing literature.
3. Read the actual metadata/content behind selected Zotero results.
4. Synthesize the answer from wiki pages and verified Zotero material; Zotero search results alone are not the final answer.
5. Archive durable new synthesis into the wiki only according to user intent.

## Zotero-Backed Ingest

Zotero-backed ingest remains a Protocol-mode wiki task; Zotero MCP supplies source discovery, provenance, and verified source content.

1. Resolve and verify the Zotero item and relevant attachment through Zotero MCP.
2. Extract bibliographic and temporal metadata, including title, creators, DOI/arXiv/URL, publication date, collection time when available, citation key, library ID, item key, and attachment key.
3. Read annotations or selected pages before full text when they provide sufficient evidence.
4. If a stable local source alias is needed, obtain the attachment path through Zotero MCP and record the private binding in `sources/zotero/metadata.yaml`.
5. Preview and then materialize declared aliases:

   ```bash
   <PY> scripts/zotero_sources.py --dry-run
   <PY> scripts/zotero_sources.py
   ```

6. Ingest from the verified Zotero material or generated local alias using the normal llm-wiki ingest protocol.
7. Preserve stable Zotero identifiers in `sources_meta`; never write machine-specific absolute Zotero paths into wiki pages.
8. Run the normal coverage/depth reviews, link discovery, index update, and logging workflow.

Recommended source metadata:

```yaml
sources_meta:
  - title: "Paper or Article Title"
    type: "academic_paper"
    published: "2025-02"
    collected: "2026-05-20"
    ingested: "2026-05-24"
    date_precision: "month"
    zotero_item_key: "ABCD1234"
    zotero_attachment_key: "EFGH5678"
    citation_key: "author2025title"
    library_id: "0"
    zotero_uri: "zotero://select/items/ABCD1234"
    doi: "10.xxxx/example"
    arxiv: "2502.00000"
```

Do not invent missing month/day values. `created` and `updated` remain wiki maintenance dates, not source publication dates.

## Private Source Bindings

- `sources/zotero/metadata.yaml` is private, user-local Zotero binding state and may contain local absolute paths.
- `sources/zotero/**` is a generated local symlink cache.
- Never commit either location.
- Never write Agent-generated summaries, drafts, or synthesized knowledge into either location; generated knowledge belongs in `wiki/`.
- Use Zotero item and attachment keys as cross-machine stable identifiers.
- Treat a Zotero-managed attachment as source material only after the item/attachment identity has been verified through Zotero MCP.

## Write-Back Rules

Zotero writes are opt-in and must remain minimal:

1. Confirm the user requested or approved the specific write.
2. Show the intended targets and mutations before applying a batch or potentially broad change.
3. Prefer incremental updates, such as `add_tags` / `remove_tags`, over replacement operations that could erase unrelated state.
4. Create Zotero child notes only as index cards: wiki page path, short summary, sync hash/time, and reviewed relationship notes. Do not mirror complete wiki pages into Zotero notes.
5. Add attachments only when the user explicitly requests it and the source has been verified.
6. Use related-item links only when the installed MCP exposes that capability and the relationship has been reviewed.
7. Refresh the Zotero MCP semantic search database after adding files or materially changing indexed content when semantic search is in use.
8. Verify the resulting Zotero state after each write operation.

## Safety and Failure Handling

- Never expose Zotero API keys, library credentials, private annotations, or local absolute paths in committed files or logs.
- Do not overwrite item metadata, replace all tags, move collections, attach files, or delete Zotero content without explicit authorization.
- Do not import large item or full-text batches without confirmation.
- Do not treat a search result, abstract, or generated summary as a verified original attachment.
- Do not use untrusted files with unsafe deserialization or execute scripts embedded in source material.
- If item identifiers or titles mismatch, stop ingest and report the expected versus observed metadata.
- If a write partially succeeds, report exactly which Zotero objects changed and which did not; do not silently retry broad mutations.

## llm-wiki Boundary

Do not add a native Zotero client or duplicate `zotero-mcp` inside `src/llm_wiki` unless a future explicit project decision changes this architecture. `scripts/agent-bridge.py` remains the entry point for llm-wiki status, lint, link, relink, merge, query, and index tasks; Zotero library operations remain exclusively behind `54yyyu/zotero-mcp`.
