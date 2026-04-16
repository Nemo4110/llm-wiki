---
name: llm-wiki
description: "Karpathy's llm-wiki pattern implementation — cumulative knowledge management for AI agents"
version: 1.1.0
author: "@yourname"
license: MIT
repository: "https://github.com/Nemo4110/llm-wiki.git"

# Supported platforms
platforms:
  - claude-code
  - openclaw
  - generic-llm-agent

# Required capabilities from host agent
capabilities:
  - filesystem-read
  - filesystem-write
  - llm-completion

# Entry points for different modes
entryPoints:
  protocol: "CLAUDE.md"
  agent-guide: "AGENTS.md"
  cli: "src/llm_wiki/commands.py"

# Hooks (optional integration)
hooks:
  available: false
  note: "Protocol mode requires no hooks. CLI mode available for scripting."

# Dependencies
dependencies:
  required: []
  optional:
    - name: python
      version: ">=3.8"
      reason: "CLI mode only"
    - name: click
      version: ">=8.0.0"
      reason: "CLI framework"
    - name: pyyaml
      version: ">=6.0"
      reason: "YAML parsing"
    - name: pymupdf
      version: ">=1.25.0"
      reason: "PDF processing (recommended)"
    - name: numpy
      version: ">=1.24.0"
      reason: "Embedding retrieval"
    - name: httpx
      version: ">=0.27.0"
      reason: "Ollama/local HTTP client for embedding"
    - name: openai
      version: ">=1.0.0"
      reason: "OpenAI embedding API"
    - name: mcp
      version: ">=1.0.0"
      reason: "MCP SDK for remote embedding providers"

# Installation methods
installation:
  - method: uv
    command: "uv venv && uv pip install -r src/requirements.txt --python .venv/Scripts/python.exe"
    note: "Fastest, recommended if uv available"
  - method: conda
    command: "conda create -n llm-wiki python=3.11 && pip install -r src/requirements.txt"
    note: "For data science environments"
  - method: pip
    command: "python -m venv .venv && pip install -r src/requirements.txt"
    note: "Standard Python"
  - method: none
    command: null
    note: "Protocol mode requires no installation"

# Core functions exposed to agent
functions:
  ingest:
    description: "Ingest source material into wiki"
    trigger: "请摄入资料"
    inputs:
      - name: source_path
        type: string
        description: "Path to source file in sources/"
    workflow:
      - Read source content
      - Extract key insights
      - Identify/create affected wiki pages
      - Update cross-references
      - Create stub pages for any new [[Dead Link]] introduced in the content
      - Append to log.md

  query:
    description: "Query wiki knowledge base"
    trigger: "查询 wiki"
    inputs:
      - name: question
        type: string
        description: "User question about wiki content"
    workflow:
      - Read wiki/index.md
      - Navigate through [[links]]
      - Synthesize answer with citations
      - Optional: archive response

  lint:
    description: "Health check for wiki"
    trigger: "检查 wiki 健康"
    checks:
      - orphan pages
      - dead links
      - stale pages
      - draft pages
      - contradictions

# File structure
structure:
  protocol: "CLAUDE.md"
  agent-guide: "AGENTS.md"
  specification: "SKILL.md"
  changelog: "log.md"
  sources: "sources/"
  wiki: "wiki/"
  assets: "assets/"
  scripts: "scripts/"
  src: "src/"
  examples: "examples/"

# Related resources
related:
  - name: "Karpathy's llm-wiki gist"
    url: "https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f"
  - name: "Sage-Wiki"
    url: "https://github.com/xoai/sage-wiki"
    note: "Alternative full-featured implementation"
---

# CLI Reference

## Protocol Mode (Recommended)

Use natural language with your agent:

```
"请摄入 sources/paper.pdf 到 wiki"
"查询 wiki: Transformer 和 RNN 有什么区别？"
"检查 wiki 健康状况"
```

## CLI Mode (Optional)

After installing dependencies:

```bash
# Show wiki status overview
python -m src.llm_wiki status

# Run health check
python -m src.llm_wiki lint

# Show help
python -m src.llm_wiki --help
```

**Note**: `ingest` and `query` commands in CLI only provide auxiliary functions (like listing pages). Actual content processing requires natural language interaction with the agent.

# LLM-Wiki

Karpathy's llm-wiki pattern implementation — cumulative knowledge management for AI agents.

> **Core Philosophy**: LLM as programmer, Wiki as codebase, User as product manager.

## Why SKILL Form?

| Dimension | Standalone App (e.g., Sage-Wiki) | This SKILL Implementation |
|-----------|----------------------------------|---------------------------|
| **Architecture** | Go + SQLite + Embedded Frontend | Pure Markdown |
| **Deployment** | Requires running service | Zero deployment |
| **Integration** | Indirect via MCP | Native commands |
| **Code Size** | ~10k lines | ~500 lines |
| **Data Format** | Proprietary | Plain text Markdown |
| **Editor** | Locked in app | Obsidian/VSCode/Any |

## Features

- 📚 **Protocol-driven**: Works with natural language (no installation required)
- 📝 **Pure Markdown**: No database, no lock-in, git-native
- 🔗 **Wiki-style links**: `[[PageName]]` format, Obsidian-compatible
- 🧠 **Cumulative learning**: Every query can create new knowledge
- 🔍 **Health checks**: Orphan pages, dead links, stale content detection
- 🖥️ **Optional CLI**: Python scripts for automation and batch operations

## Quick Start

```bash
# 1. Clone
git clone https://github.com/Nemo4110/llm-wiki.git
cd llm-wiki

# 2. Add source material
cp ~/Downloads/paper.pdf sources/

# 3. Tell your agent
"请摄入 sources/paper.pdf 到 wiki"
```

## Installation

### Protocol Mode (Recommended)
No installation needed. Agent reads `CLAUDE.md` and operates directly.

### CLI Mode (Optional)

#### Using uv (Fastest)
```bash
# Create virtual environment and install dependencies
uv venv
uv pip install -r src/requirements.txt --python .venv/Scripts/python.exe

# Activate environment (Windows)
.venv\Scripts\activate
# Or Linux/macOS
source .venv/bin/activate
```

#### Using conda
```bash
# Create environment
conda create -n llm-wiki python=3.11

# Activate environment
conda activate llm-wiki

# Install dependencies
pip install -r src/requirements.txt
```

#### Using pip
```bash
# Create virtual environment
python -m venv .venv

# Activate environment
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r src/requirements.txt
```

#### Verify Installation
```bash
python -c "from src.llm_wiki.core import WikiManager; print('✓ Installation successful')"
```

**Important Dependency Notes**:

| Dependency | Version | Purpose | Notes |
|------------|---------|---------|-------|
| `click` | >=8.0.0 | CLI framework | - |
| `pyyaml` | >=6.0 | YAML parsing | - |
| `pymupdf` | >=1.25.0 | PDF processing | Primary PDF engine, best for CJK |

**Optional dependencies** (for enhanced features):
- `numpy >=1.24.0` — Vector operations for embedding retrieval
- `httpx >=0.27.0` — HTTP client for Ollama/local services
- `openai >=1.0.0` — OpenAI embedding API
- `mcp >=1.0.0` — MCP SDK for remote embedding providers

**Fallback PDF dependency**:
- `pdfplumber >=0.11.8` — Table extraction fallback (security version required for CVE-2025-64512)
- `pdfminer.six >=20251107` — PDF底层库 fallback

## Project Structure

```
llm-wiki/
├── CLAUDE.md           # ⭐ Core protocol: Agent behavior guidelines
├── AGENTS.md           # Agent implementation guide (CLI usage)
├── SKILL.md            # This file
├── log.md              # Timeline log (append-only)
├── sources/            # Raw materials (user-managed, Agent read-only)
│   └── README.md
├── wiki/               # Generated knowledge pages (Agent-managed)
│   ├── index.md        # Entry index
│   └── *.md            # Topic pages
├── assets/             # Templates and configuration
│   ├── page_template.md
│   └── ingest_rules.md
├── src/                # SKILL implementation (optional, for CLI)
│   ├── llm_wiki/
│   └── requirements.txt
├── scripts/            # Auxiliary scripts
├── hooks/              # Platform hooks (optional)
└── examples/           # Example wiki
```

**About `sources/`**: Excluded from git by default to avoid repository bloat. Wiki only retains extracted knowledge; original files are managed separately (cloud storage, Zotero, etc.). See `sources/README.md` for tracking specific files.

## How It Works

### Data Flow

```
+----------+     +--------------------+     +--------------+
| sources/ |---->|   LLM Processing   |---->|    wiki/     |
|  (Raw)   |     | (Extract + Link)   |     | (Structured) |
+----------+     +--------------------+     +--------------+
                          |
                          v
                    +----------+
                    |  log.md  |
                    | (Record) |
                    +----------+
```

### Key Design

1. **CLAUDE.md as Protocol**: Defines Agent behavior standards, anyone/any Agent can follow
2. **Pure Markdown**: No database, no lock-in, native git version control
3. **Bidirectional Links**: `[[PageName]]` format, compatible with Obsidian
4. **Cumulative Learning**: Each query can generate new wiki pages, knowledge continuously accumulates

## Query Mechanism

### Current Implementation: Symbolic Navigation + LLM Synthesis (Default)

By default, this SKILL **does not require Embedding/vector retrieval**. Queries are completed through:

```
User asks question
         |
         v
+-------------------------------+
|  1. Read index.md             |  <-- Human/Agent-maintained category index
|     Locate relevant topics    |
+-------------------------------+
         |
         v
+-------------------------------+
|  2. Read relevant pages       |  <-- Discover associations through [[links]]
|     and their link neighbors  |
+-------------------------------+
         |
         v
+-------------------------------+
|  3. LLM Synthesis             |  <-- Generate answers based on read content
|     Generate with citations   |  Citation format: [[PageName]]
+-------------------------------+
```

**Optional Enhancement**: After enabling `config.yaml` embedding settings, CLI `query --semantic` adds hybrid search (Keyword Match + Vector Search + Link Traversal) for faster, more accurate retrieval.

**Example Flow**:

User asks: "What is LoRA?"

1. **Agent reads** `wiki/index.md`, finds `[[LoRA]]` under "AI/ML" topic
2. **Agent reads** `wiki/LoRA.md`, discovers links to `[[Fine-tuning]]`, `[[Adapter]]`
3. **Agent synthesizes** answer:
   > LoRA (Low-Rank Adaptation) is a parameter-efficient fine-tuning method — see [[LoRA]].
   > Compared to traditional [[Fine-tuning]], it only trains low-rank matrices...

### Why is Embedding Optional?

| Consideration | Current Solution | Embedding Solution |
|---------------|------------------|-------------------|
| **Dependencies** | Zero external dependencies | Requires Embedding API or local model |
| **Cost** | No additional fees | Charged per token/request |
| **Privacy** | Data not uploaded | Must send content to external service |
| **Accuracy** | Precise links, explainable | Approximate similarity, may retrieve irrelevant content |
| **Scale** | Suitable for 0-500 pages | Essential for large scale (1000+ pages) |

**Conclusion**: For personal/small team knowledge bases, maintaining `index.md` and page links is simpler and more effective than introducing Embedding. Embedding is available as an opt-in CLI enhancement when scale demands it.

### When to Use Embedding?

Consider enabling `config.yaml` embedding settings when your wiki shows:
- [ ] Page count > 500, manual indexing hard to maintain
- [ ] Queries are mostly fuzzy semantic ("that paper about optimization...")
- [ ] Need cross-topic associations (user didn't mention keywords, but semantically related)

See [ROADMAP.md](ROADMAP.md) for details.

## Example Workflows

### Scenario 1: Researching New Domain

```bash
# Day 1: Add materials
sources/
├── 2026-04-10-transformer-paper.pdf
└── 2026-04-10-lora-blog.md
```

```
User: Please ingest new materials
Claude: Processed 2 materials
  - Created [[Transformer]] — Attention mechanism architecture
  - Created [[LoRA]] — Low-rank adaptation
  - Created [[Self-Attention]] — Self-attention details
  - Updated wiki/index.md
```

### Scenario 2: Deep Exploration

```
User: What's the difference between LoRA and full fine-tuning?

Claude (reads wiki/index.md → finds [[LoRA]] → synthesizes answer):

Based on our wiki:

**LoRA** — [[LoRA]]
- Freezes pre-trained weights, only trains low-rank matrices
- Parameter count reduced ~10,000x

**Full Fine-tuning**
- Updates all parameters
- High computational cost

Key differences:
1. Parameters: LoRA only trains 0.1%~1% of parameters [[Parameter Efficiency]]
2. Storage: LoRA only saves adapters, not full model
3. Composition: Multiple LoRAs can be stacked [[LoRA Composition]]

Was this helpful? Should I archive this answer to wiki?
```

### Scenario 3: Knowledge Accumulation

```
User: Yes, archive this answer

Claude: Created [[LoRA vs Full Fine-tuning]]
- Extracted comparison points from conversation
- Linked to [[LoRA]] and [[Fine-tuning]]
- Added to FAQ section in wiki/index.md
```

## Using with Obsidian

1. Open `wiki/` directory in Obsidian
2. Enjoy graph view, quick navigation, beautiful rendering
3. Claude Code handles maintenance, Obsidian handles reading and thinking

## Comparison with Alternatives

| Solution | Characteristics | Best For |
|----------|----------------|----------|
| **This SKILL** | Zero dependencies, pure text, Claude Code native | Personal knowledge management, research notes |
| Sage-Wiki | Full-featured, multimodal, standalone app | Team knowledge base, enterprise deployment |
| Obsidian + Plugins | Strong visualization, rich community | Existing Obsidian workflow |
| Notion/Logseq | Collaborative, real-time sync | Multi-user collaboration, mobile access |

## Documentation

- [CLAUDE.md](CLAUDE.md) — User-facing protocol (read this first)
- [AGENTS.md](AGENTS.md) — Implementation guide for agent developers
- [SKILL.md](SKILL.md) — This file, machine-readable specification
- [ROADMAP.md](ROADMAP.md) — Future plans

## Contributing

Issues and PRs welcome!

### Current TODO

- [ ] MCP server wrapper (for other Agents)
- [ ] Obsidian plugin (one-click sync)
- [x] Incremental embedding for faster retrieval
- [ ] Multi-language support

## License

MIT — free to use, modify, and distribute.

---

*Inspired by [Karpathy's llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)*
