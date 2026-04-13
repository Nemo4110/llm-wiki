# LLM-Wiki SKILL Specification

> 规范格式的技能描述文件，供 Claude Code、OpenClaw 等 Agent 平台解析。

## Metadata

| Field | Value |
|-------|-------|
| **Name** | llm-wiki |
| **Version** | 1.0.0 |
| **Description** | Karpathy 的 llm-wiki 模式实现 —— 累积式知识管理 |
| **Author** | @yourname |
| **License** | MIT |
| **Repository** | https://github.com/yourname/llm-wiki |

## Capabilities

### Core Functions

| Function | Trigger | Description |
|----------|---------|-------------|
| `ingest` | "请摄入资料" / `/wiki-ingest <path>` | 将原始资料转换为 wiki 页面 |
| `query` | "查询 wiki" / `/wiki-query <question>` | 从 wiki 中检索并综合回答 |
| `lint` | "检查 wiki 健康" / `/wiki-lint` | 检查孤儿页面、死链、陈旧内容 |

### Supported Inputs

- **Documents**: PDF, Markdown, TXT, DOCX (via extraction)
- **Images**: PNG, JPG (via vision)
- **Code files**: Python, JavaScript, etc.
- **Web links**: URLs or pasted content

### Output Format

- Markdown pages with YAML frontmatter
- Wiki-style cross-references: `[[PageName]]`
- Chronological log: `log.md`

## Protocol

### Ingest Workflow

1. **Read** source material from `sources/`
2. **Extract** key insights using LLM
3. **Identify** affected wiki pages (create or update)
4. **Update** pages with merged information
5. **Maintain** cross-references using `[[Link]]` syntax
6. **Log** activity to `log.md`

### Query Workflow

1. **Read** `wiki/index.md` to locate relevant topics
2. **Navigate** through `[[links]]` to discover related pages
3. **Synthesize** answer with citations: `[[PageName]]`
4. **Archive** valuable responses back to wiki (optional)

### Lint Workflow

1. **Scan** all pages in `wiki/`
2. **Detect** issues: orphans, dead links, stale pages, drafts
3. **Report** findings with fix suggestions

## File Structure

```
llm-wiki/
├── CLAUDE.md           # User-facing protocol (REQUIRED READ)
├── AGENTS.md           # Agent implementation guide
├── SKILL.md            # This file
├── log.md              # Activity log
├── sources/            # Raw materials (user-managed)
├── wiki/               # Generated knowledge pages
│   ├── index.md        # Entry point
│   └── *.md            # Topic pages
├── schema/             # Templates and rules
└── src/                # CLI implementation (optional)
```

## Dependencies

### Required (Protocol Mode)
- None. Operates on pure Markdown files.

### Optional (CLI Mode)
- Python 3.8+
- `click>=8.0.0`
- `pyyaml>=6.0`

### Installation Methods
1. **uv** (fastest): `uv venv && uv pip install -r src/requirements.txt`
2. **conda**: `conda create -n llm-wiki python=3.11 && pip install -r src/requirements.txt`
3. **pip**: `python -m venv .venv && pip install -r src/requirements.txt`

## Entry Points

### Natural Language (Recommended)

Agent parses user intent and executes protocol directly:

```
User: "请摄入 sources/paper.pdf"
Agent: [Reads CLAUDE.md] → [Executes ingest workflow] → [Updates files]
```

### CLI Commands (Optional)

If dependencies installed:

```bash
# Using venv Python
.venv/Scripts/python -c "from src.llm_wiki.core import WikiManager; ..."

# Direct module execution (when __main__ implemented)
python -m src.llm_wiki status
python -m src.llm_wiki lint
```

## Modes of Operation

| Mode | Dependencies | Use Case |
|------|--------------|----------|
| **Protocol** | None | Natural language interaction via Agent |
| **CLI** | Python + click | Scripting, batch operations, status checks |

## Integration Notes

### For Claude Code
- Primary: Natural language triggers (ingest, query, lint)
- Fallback: Direct file operations if CLI unavailable
- Context files: `CLAUDE.md`, `wiki/index.md`, `log.md`

### For OpenClaw
- Same protocol as Claude Code
- May expose as MCP tools in future

### For Other Agents
- Read `CLAUDE.md` for user protocol
- Read `AGENTS.md` for implementation guidance
- Implement core workflows in agent's native language

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-04-13 | Initial release |

## See Also

- [Karpathy's llm-wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [Sage-Wiki](https://github.com/xoai/sage-wiki) - Alternative full-featured implementation
