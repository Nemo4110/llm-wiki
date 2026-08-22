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

## Access Mode, Authority, and Synchronization State

Treat Zotero as two related but distinct planes: **metadata state** and **attachment-file state**. Before any Zotero write or file-backed ingest, determine both planes instead of relying on a label such as "hybrid mode":

```text
metadata_authority     = local | web
metadata_read_backend  = local | web
metadata_write_backend = local | web | unavailable
metadata_sync_state    = disabled | pending | caught_up | divergent | unknown

attachment_authority   = local_machine | zotero_file_sync | webdav | linked_external | unknown
attachment_access      = local_path | local_api_stream | remote_download | indexed_fulltext_only | unavailable
```

- **Metadata authority** is the item/collection/tag state the user considers canonical.
- **Metadata read backend** is where the current MCP tool obtains the state used to make a decision.
- **Metadata write backend** is where the mutation is actually applied.
- **Metadata sync state** describes whether the authority and the write backend are known to agree.
- **Attachment authority** identifies where the actual file bytes are expected to exist.
- **Attachment access** describes what the current MCP session can actually retrieve. It is a capability statement, not an existence statement.

Use the following metadata write gate:

| Authority | Read backend | Write backend | Sync state | Decision |
| --- | --- | --- | --- | --- |
| Web | Web | Web | Any | Writes may proceed after the normal capability gate |
| Local | Local or Web | Web | `caught_up` | Writes may proceed, but completion requires a synchronization barrier |
| Local | Any | Web | `disabled` or `pending` | A successful Web write is cloud-pending, not locally complete; do not start broad writes while synchronization is pending |
| Local | Any | Web | `divergent` or `unknown` | Stop writes and reconcile or re-audit first |
| Any | Any | `unavailable` | Read-only work only |

Do not infer backend consistency from configuration values alone. A valid API key, an exposed write tool, or a successful single-item write proves only that one route is writable; it does not prove that local and Web state agree.

### Backend Consistency Gate

For a write task, perform the following checks when the relevant state is observable:

1. Discover the active library and resolve the intended collection in that library.
2. Read a known item and inspect its tags and `Collections` field.
3. Compare the observed state with the user-designated authority. A collection visible only on one backend is evidence of divergence, not a missing user object.
4. When write authorization is uncertain, use a unique temporary sentinel tag on one approved low-risk item: add it, read it from the write backend, remove it, and verify removal.
5. Treat the sentinel as a narrow authorization test. It does not validate batch-version behavior, synchronization, overlapping writes, or local visibility.
6. After changing MCP configuration, rotating credentials, switching libraries or modes, restarting Zotero/Codex/MCP, or enabling synchronization, rerun this gate.

> **Hybrid-mode warning:** a connected server may read tags from local Zotero while routing writes through the Web API. If those states differ, a read-modify-write implementation can send an outdated complete tag set to Web and overwrite a preceding batch. Do not perform overlapping writes to the same items across inconsistent backends.

## Setup Reference

The upstream project currently supports local, web, and hybrid access modes. Follow its current setup documentation rather than copying environment-specific configuration into llm-wiki.

Typical upstream setup commands are:

```bash
uv tool install zotero-mcp-server
zotero-mcp setup
```

Local read workflows require Zotero Desktop with its local API enabled. Write workflows generally require Zotero Web API credentials or another write-capable mode supported by the connected server. Never print, commit, or copy Zotero API keys or other credentials into project files.

### Configuration Ownership

Do not assume that `~/.config/zotero-mcp/config.json` controls the active MCP access mode. In zotero-mcp 0.9.x, that file primarily stores semantic-search, database-path, extraction, and index-update settings. Local/Web mode and Web credentials are normally supplied by the MCP client's process environment.

For Codex, inspect the configured server entry in `~/.codex/config.toml` (or the equivalent host-managed MCP configuration). A hybrid configuration keeps local access enabled while retaining Web credentials for write-capable operations:

```toml
[mcp_servers.zotero-mcp]
command = "zotero-mcp"

[mcp_servers.zotero-mcp.env]
ZOTERO_LOCAL = "true"
ZOTERO_DB_PATH = "<absolute path to the active zotero.sqlite>"
ZOTERO_API_KEY = "<secret provided only in local MCP configuration>"
ZOTERO_LIBRARY_ID = "<user or group library ID>"
ZOTERO_LIBRARY_TYPE = "user"
ZOTERO_EMBEDDING_MODEL = "default"
```

A minimal semantic configuration can omit runtime-generated fields such as last-update timestamps and sync versions:

```json
{
  "semantic_search": {
    "zotero_db_path": "<absolute path to the active zotero.sqlite>",
    "embedding_model": "default",
    "update_config": {
      "auto_update": true,
      "update_frequency": "startup",
      "update_days": 7
    },
    "extraction": {
      "pdf_max_pages": 10
    }
  }
}
```

The same machine can contain configuration for several MCP clients. `zotero-mcp setup-info` may describe a Claude Desktop entry while Codex launches the server with different environment values. Treat the environment of the client that started the current MCP process as authoritative. After changing it, restart that client/MCP process and rerun the backend-consistency gate.

A practical post-restart smoke test should verify each required route independently: discover the library, read one known item, resolve one known local attachment path, exercise the exact PDF endpoint needed by the task, and—only when writes are authorized—add/read/remove/read a unique sentinel tag. Passing one route does not imply that the others are available.

### Data Sync, File Sync, and Local Authority

Zotero data synchronization and attachment-file synchronization are separate concerns. Zotero Data Sync covers bibliographic items, collections, tags, and notes; file synchronization covers stored attachment files. A user may enable Data Sync while leaving Zotero File Sync disabled. See the official [Zotero Sync documentation](https://www.zotero.org/support/sync) for current behavior.

For a local-authoritative workflow in which MCP writes through the Web API:

1. Keep the Zotero Desktop library as the declared authority.
2. Enable Zotero Data Sync so metadata writes can return to Desktop.
3. File Sync may remain disabled when the user does not want Zotero-hosted attachment storage.
4. Treat Web writes as pending until synchronization completes and the post-sync audit passes.
5. Do not issue additional broad writes while the first synchronization or a conflict merge is still in progress.

Follow the official [Zotero data-directory guidance](https://www.zotero.org/support/zotero_data) and do not place the active Zotero data directory or `zotero.sqlite` in OneDrive, Dropbox, or another generic file-sync directory. Those tools operate at the file level and may copy a live database in an inconsistent state. If cloud storage is used for attachments, prefer a deliberately configured linked-attachment directory while keeping the Zotero database in a normal local data directory. Agents may diagnose paths read-only, but must not automatically relocate a live database or invoke destructive synchronization reset options.

If local and Web libraries have already diverged, stop mutations, back up the local authority, let the user choose the reconciliation direction in Zotero, and re-audit all counts, keys, tags, and memberships after synchronization.

### Attachment Existence vs. Path Resolution

Attachment metadata and attachment file bytes can have different availability. Zotero Data Sync may synchronize an attachment item, filename, and parent relationship without synchronizing the file bytes. Conversely, a file may exist in the current machine's Zotero storage while a Web-only MCP session cannot return its local path.

Interpret attachment errors narrowly:

- `zotero_get_attachment_path requires local mode` means the current MCP mode cannot resolve local filesystem paths. It does **not** prove that the file is absent from the machine.
- A Web API file `404` may mean Zotero File Sync is disabled or the bytes were never uploaded. It does **not** prove that the corresponding local stored or linked file is absent.
- `indexed_fulltext_only` means text can be read through Zotero's full-text index even though the original file path or bytes are not available through the current tool route.
- A successfully resolved local path proves path resolution for that attachment only. It does not prove that optional PDF features are installed. For example, selected-page reading may work while outline or layout extraction fails because the corresponding PDF extra is unavailable; test the exact endpoint required by the task.

For a synchronized metadata / local-file workflow, prefer this responsibility split:

1. Resolve item, collection, tags, attachment key, filename, and bibliographic provenance from the declared metadata authority. Web metadata is a reasonable operational authority only when Data Sync is enabled, caught up, and the user has selected it as authoritative.
2. Resolve actual source bytes from the machine where they are stored, using a local- or hybrid-mode Zotero MCP capability. Do not assume Zotero File Sync is enabled.
3. Join metadata and file identity by stable item/attachment keys plus filename or content identity; do not join by title alone.
4. If the current MCP is Web-only but the user reports a local file, record `local-path capability unavailable in current mode` and reconfigure/restart Zotero MCP with approval before materializing an alias. Do not silently scan Zotero storage or bypass MCP.
5. Re-run the capability gate after changing `ZOTERO_LOCAL` or switching between local, Web, and hybrid access.

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
2. Record the collection key, backend, item count, and observation time; collection snapshots become stale after synchronization or user edits.
3. Produce a candidate list containing title, creators, date, item type, Zotero item key, and citation key when available.
4. Treat collection searches as candidate discovery. Endpoint behavior around parent/child collections can vary by tool or version; do not infer direct membership solely because a title appears in a scoped search.
5. Before moving or removing membership, read each selected item's metadata and treat its explicit `Collections` field as the membership source of truth.
6. Use semantic search only as candidate discovery and only when its database is ready.
7. Select relevant items before reading full text; do not bulk-read an entire collection by default.
8. For batch ingest, group sources by reusable topic, mechanism, or historical phase instead of mechanically creating one wiki page per Zotero item.

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
   - **Local-path capability unavailable in the current mode:** do not report the attachment as physically absent. If local bytes are expected, request an approved local/hybrid reconfiguration and rerun the capability gate.
   - **Verified indexed text but no readable original bytes:** do not create a private binding or symlink. Ingest directly from verified annotations, selected pages, or full text returned through Zotero MCP, and record the access limitation.
   - **Attachment identity or content unavailable:** stop source-dependent ingest for that item and report the blocker.
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

## llm-wiki Tag Semantics

Use llm-wiki-managed tags as explicit workflow state, not as interchangeable labels:

| Tag form | Meaning | Add when |
| --- | --- | --- |
| `llm-wiki:<scope>` | Reviewed domain or collection classification | The classification audit has passed |
| `llm-wiki:<canonical-topic>` | Stable topic allocation, normally aligned with a reusable wiki topic/page | The topic assignment has been reviewed |
| `llm-wiki:ingested` | The source has completed the llm-wiki ingest protocol | Wiki drafting, source coverage, depth review, linking, indexing, and logging have completed |
| `llm-wiki:write-sentinel-*` | Temporary authorization test | Only during a write probe; remove and verify removal immediately |

Collection membership does not imply ingest completion. Items that have been classified or moved but not yet synthesized may receive scope and topic tags, but must not receive `llm-wiki:ingested`. Preserve user-managed tags and use incremental additions/removals rather than replacing the complete tag list.

## Write-Back and Idempotency Rules

Zotero writes are opt-in, minimal, and idempotent where the exposed tools support it:

1. Confirm the user requested or approved the specific write.
2. Show the intended targets, selection rule, source and target collection keys, and mutations before applying a batch or potentially broad change.
3. Before adding an item, search for an existing match by DOI, ISBN, URL, arXiv ID, or another stable identifier.
4. When an add tool exposes `if_exists` or equivalent reuse/skip behavior, prefer an idempotent mode for automated workflows. Do not use a duplicate-always mode unless the user explicitly requests a second item.
5. Prefer incremental updates, such as `add_tags` / `remove_tags` and collection add/remove operations, over whole-field or whole-membership replacement that could erase unrelated state. An incremental tool interface does not by itself prove that the backend implementation is atomic.
6. Serialize writes that touch the same item. Do not run overlapping tag or membership updates in parallel unless the sets are disjoint and the backend behavior has been verified.
7. Re-read from the write backend after every mutation. A tool response such as "items updated" is not sufficient verification.
8. Create Zotero child notes only as index cards: wiki page path, short summary, sync hash/time, and reviewed relationship notes. Do not mirror complete wiki pages into Zotero notes.
9. Add attachments only when the user explicitly requests it and the source has been verified. Check existing attachments by stable source, filename, or content identity when the tool exposes those checks.
10. Use related-item links only when the connected MCP exposes the relation toolset, write access is available, and the relationship has been reviewed.
11. Refresh the Zotero MCP semantic search database after adding files or materially changing indexed content when semantic search is in use.
12. When local is authoritative and Web is the write backend, wait for the synchronization barrier and re-audit the local-visible state before reporting local completion.

### Safe Collection Membership Migration

For moving items from a source collection to a target collection, use a two-phase migration:

1. Resolve both collection keys in the active library.
2. Snapshot each candidate item's explicit `Collections` field and preserve unrelated memberships.
3. Classify candidates and separate high-confidence, ambiguous, and excluded items.
4. Add the approved items to the target collection only.
5. Re-read and verify target membership for every item.
6. Remove only the source collection membership. Never replace the complete collection list.
7. Re-read and verify that the target is present, the source is absent, and all unrelated memberships remain.
8. Recount source and target collections and verify expected count deltas, accounting for items already present in the target.
9. Sample items with PDFs, notes, annotations, or secondary collection memberships and verify those children and memberships remain intact.

Do not combine the add and remove phases in one unverified operation. A collection migration changes membership only; it must not trash items or attachments.

### Synchronization Barriers and State Invalidation

Treat earlier observations as stale after any of the following:

- enabling or resuming Zotero Data Sync;
- the first synchronization between previously independent local and Web libraries;
- changing `ZOTERO_LOCAL`, credentials, library type, or library ID;
- restarting Zotero Desktop, Codex, or the MCP server;
- switching user/group libraries;
- a user batch-editing the same collections or items;
- a Zotero synchronization reset or conflict resolution.

After such an event, rediscover the library and collection keys, recount relevant collections, and inspect representative item tags and `Collections` fields before continuing. Do not issue broad writes while synchronization is pending or conflict resolution is unknown.

### Verification Report

For a broad write, report enough evidence to reconstruct the state transition:

```text
Metadata authority: local | web
Metadata read backend: local | web
Metadata write backend: local | web
Metadata sync state: disabled | pending | caught_up | divergent | unknown
Attachment authority: local_machine | zotero_file_sync | webdav | linked_external | unknown
Attachment access: local_path | local_api_stream | remote_download | indexed_fulltext_only | unavailable
Source collection and count: ...
Target collection and count: ...
Selection rule and candidate count: ...
Items updated / skipped / failed: ...
Post-write tag or membership verification: ...
Unrelated memberships and child objects sampled: ...
Pending local synchronization: yes | no
```

If local is authoritative, distinguish `cloud write succeeded` from `verified locally`.

## Safety and Failure Handling

- Never expose Zotero API keys, library credentials, private annotations, or local absolute paths in committed files or logs.
- Do not overwrite item metadata, replace all tags, move collections, attach files, or delete Zotero content without explicit authorization.
- Do not import large item or full-text batches without confirmation.
- Do not treat a search result, abstract, or generated summary as a verified original attachment.
- Do not use untrusted files with unsafe deserialization or execute scripts embedded in source material.
- If item identifiers or titles mismatch, stop ingest and report the expected versus observed metadata.
- If a write partially succeeds, report exactly which Zotero objects changed and which did not; do not silently retry broad mutations.
- If an API key or credential is exposed, stop writes, do not repeat the secret, require revocation and rotation, check project files/logs for leakage, restart the Agent host/MCP so the new credential is loaded, and rerun the backend-consistency gate before resuming.
- Do not treat "configuration updated" as proof that a running MCP process has reloaded it.
- Do not use direct SQLite, direct Web API, or an alternative Zotero client to repair a synchronization or capability failure.

## llm-wiki Boundary

Do not add a native Zotero client or duplicate `zotero-mcp` inside `src/llm_wiki` unless a future explicit project decision changes this architecture. `scripts/agent-bridge.py` remains the entry point for llm-wiki status, lint, link, relink, merge, query, and index tasks; Zotero library operations remain exclusively behind `54yyyu/zotero-mcp`.
