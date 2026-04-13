---
name: llm-wiki
description: "Karpathy's llm-wiki pattern implementation — cumulative knowledge management for AI agents"
version: 1.0.0
author: "@yourname"
license: MIT
repository: "https://github.com/yourname/llm-wiki"

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

# LLM-Wiki SKILL

Cumulative knowledge management system based on [Karpathy's llm-wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

## Philosophy

- **LLM as programmer, Wiki as codebase**
- **User curates sources, asks questions**
- **Agent handles summarizing, cross-referencing, filing**
- **Accumulation over retrieval**: every interaction leaves lasting value

## Quick Start

```bash
# 1. Clone
git clone https://github.com/yourname/llm-wiki.git
cd llm-wiki

# 2. Add source material
cp ~/Downloads/paper.pdf sources/

# 3. Tell your agent
"请摄入 sources/paper.pdf 到 wiki"
```

## Modes of Operation

| Mode | Dependencies | Best For |
|------|--------------|----------|
| **Protocol** | None | Natural language via Claude Code, OpenClaw |
| **CLI** | Python + click | Scripting, batch operations |

## Documentation

- `CLAUDE.md` — User-facing protocol (read this first)
- `AGENTS.md` — Implementation guide for agent developers
- `SKILL.md` — This file, machine-readable specification

## License

MIT — free to use, modify, and distribute.
