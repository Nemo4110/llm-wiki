# Zotero MCP Operating Protocol

> Canonical Agent instructions for every Zotero operation in llm-wiki.
>
> **Required integration:** [`54yyyu/zotero-mcp`](https://github.com/54yyyu/zotero-mcp)
>
> **Upstream compatibility last reviewed:** 2026-08-13. The tools actually exposed by the connected MCP server take precedence over examples in this document.

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

The `zotero-mcp` CLI may be used for installation, upgrades, setup, and diagnostics. Zotero library reads, writes, and semantic-index maintenance should use the connected MCP tool surface. Use a CLI maintenance command only when the required MCP maintenance tool is unavailable and the user has approved that fallback. Installing, updating, or reconfiguring `zotero-mcp` requires user confirmation under the normal dependency and external-service rules.

## Compatibility and Capability Gate

Before every Zotero task:

1. Verify that the configured MCP integration is intended to be an installation of `54yyyu/zotero-mcp` and that its Zotero tools are exposed in the current Agent session. If the host does not expose package provenance, verify the expected capability surface and state that repository provenance could not be independently confirmed.
2. Verify access to the intended Zotero library. Discover libraries before switching; do not guess a library ID or type.
3. For read-only work, verify the specific path needed by the task, such as collection search, item metadata, annotations, attachment paths, or full text.
4. For write work, verify the exact write tool and authorization before changing anything. Note creation/update, incremental tag updates, item metadata changes, collection membership changes, attachment uploads, annotations, and related-item operations are separate capability gates.
5. Use only capabilities actually exposed by the connected `zotero-mcp` instance. Do not infer a tool exists from this document, an old example, or another installation.
6. When observable, distinguish whether a capability is not installed, not exposed by the configured toolsets, not configured, unavailable in the active access mode, or unauthorized.

| Workflow | Required capability | If unavailable |
| --- | --- | --- |
| Metadata search | Search and item-metadata tools | Stop Zotero discovery and report the blocker |
| Semantic discovery | Semantic-search tools and a ready search database | Fall back to metadata, tag, or collection search |
| Local source alias | A readable local attachment path | Ingest through verified MCP content without creating an alias |
| PDF outline/page/layout work | The relevant PDF tools and optional dependencies | Use annotations or full text when sufficient; otherwise report the limitation |
| Related-item synchronization | Relation tools exposed by the configured toolsets plus write access | Preserve the reviewed relationship only in the wiki |
| Any Zotero write | A write-capable access mode and the exact write tool | Stop Zotero-side writes and continue only with useful wiki-local work |

If `zotero-mcp` is missing, unreachable, unauthorized, connected to the wrong library, or lacks the required tool:

- stop the affected Zotero-side operation;
- state the exact blocker and failed capability gate;
- do not fall back to another Zotero integration or direct API/database access;
- continue only with useful wiki-local work that does not require that Zotero capability.

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
4. Choose the source path according to the connected access mode:
   - **Readable local attachment path available:** verify that the file exists and matches the Zotero item, then optionally create a stable local alias as described below.
   - **No readable local attachment path:** do not create a private binding or symlink. Ingest directly from verified annotations, selected pages, or full text returned through Zotero MCP.
5. Ingest from the verified Zotero material or generated local alias using the normal llm-wiki ingest protocol.
6. Preserve stable Zotero identifiers in `sources_meta`; never write machine-specific absolute Zotero paths into wiki pages.
7. Run the normal coverage/depth reviews, link discovery, index update, and logging workflow.

A local alias is an optional convenience, not a prerequisite for Zotero-backed ingest. When it is useful, record the verified attachment path in `sources/zotero/metadata.yaml`, then preview and materialize the declared aliases:

```bash
<PY> scripts/zotero_sources.py --dry-run
<PY> scripts/zotero_sources.py
```

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
    zotero_uri: "<URI returned or independently verified through Zotero MCP>"
    doi: "10.xxxx/example"
    arxiv: "2502.00000"
```

Do not invent missing month/day values. `created` and `updated` remain wiki maintenance dates, not source publication dates. Preserve `zotero_uri` only when Zotero MCP returns it or it has been independently verified; do not synthesize a URI from an item key alone. Omit the field when no verified URI is available.

## Private Source Bindings

Use this version-1 schema when a verified local attachment path is available:

```yaml
version: 1
collections:
  - name: "Collection Name"
    zotero_collection_key: "LTECJSFB"
    items:
      - title: "Paper Title"
        zotero_item_key: "9HQB5NEF"
        attachments:
          - zotero_attachment_key: "RTMTYN5Q"
            content_type: "application/pdf"
            filename: "paper.pdf"
            local_path: "C:/Zotero/storage/RTMTYN5Q/paper.pdf"
            source_alias: "sources/zotero/Collection-Name/9HQB5NEF/RTMTYN5Q.pdf"
```

Binding rules:

- `sources/zotero/metadata.yaml` is private, user-local Zotero binding state and may contain local absolute paths.
- `local_path` must identify a readable file on the current machine and must be obtained or verified through Zotero MCP.
- `source_alias` must be relative to the project root and remain strictly below `sources/zotero/`.
- `sources/zotero/**` is a generated local symlink cache. Never commit the metadata file or the cache.
- Never write Agent-generated summaries, drafts, or synthesized knowledge into either location; generated knowledge belongs in `wiki/`.
- Use Zotero item and attachment keys as cross-machine stable identifiers.
- Treat a Zotero-managed attachment as source material only after the item/attachment identity has been verified through Zotero MCP.
- Always run `scripts/zotero_sources.py --dry-run` before materializing aliases.
- Use `--force` only to replace an existing symlink that points to a different verified source. The helper refuses to replace ordinary files, and Agents must not bypass that safeguard.

## Write-Back and Idempotency Rules

Zotero writes are opt-in, minimal, and idempotent where the exposed tools support it:

1. Confirm the user requested or approved the specific write.
2. Show the intended targets and mutations before applying a batch or potentially broad change.
3. Before adding an item, search for an existing match by DOI, ISBN, URL, arXiv ID, or another stable identifier.
4. When an add tool exposes `if_exists` or equivalent reuse/skip behavior, prefer an idempotent mode for automated workflows. Do not use a duplicate-always mode unless the user explicitly requests a second item.
5. Prefer incremental updates, such as `add_tags` / `remove_tags` and collection add/remove operations, over whole-field or whole-membership replacement that could erase unrelated state.
6. Create Zotero child notes only as index cards: wiki page path, short summary, sync hash/time, and reviewed relationship notes. Do not mirror complete wiki pages into Zotero notes.
7. Add attachments only when the user explicitly requests it and the source has been verified. Check existing attachments by stable source, filename, or content identity when the tool exposes those checks.
8. Use related-item links only when the connected MCP exposes the relation toolset, write access is available, and the relationship has been reviewed.
9. Refresh the Zotero MCP semantic search database after adding files or materially changing indexed content when semantic search is in use.
10. Re-read the affected item, note, annotation, attachment, tags, or collection membership after every write and verify the resulting state.

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
