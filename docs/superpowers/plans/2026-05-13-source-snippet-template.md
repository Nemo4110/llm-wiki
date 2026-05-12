# Source Snippet Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert llm-wiki from a paper-specific page template to a single knowledge-first page template with source-type snippets.

**Architecture:** Keep one physical wiki page per knowledge topic. `assets/page_template.md` defines the stable knowledge-page skeleton; `assets/source_snippets.md` defines optional source-note sections selected by source type; `assets/ingest_rules.md` explains how agents choose page targets, source snippets, and detail depth.

**Tech Stack:** Markdown protocol files, git, existing Python agent bridge for health checks.

---

## File Structure

- Modify: `assets/page_template.md` — replace paper-specific structure with knowledge-first master template and snippet insertion point.
- Create: `assets/source_snippets.md` — define snippet library for academic papers, technical articles, code repositories, notes, documentation, books, and other sources.
- Modify: `assets/ingest_rules.md` — document the page-first/source-type-second/detail-depth-third ingest decision flow.
- Verify: `scripts/agent-bridge.py` — run status/lint/check if available to ensure docs remain coherent.
- Test artifact: create a temporary sample wiki draft from a recent Meta recommender-systems paper, verify the template supports it, then remove or avoid committing the temporary page unless explicitly valuable.

### Task 1: Update the master page template

**Files:**
- Modify: `assets/page_template.md`

- [ ] **Step 1: Replace paper-specific sections with the knowledge-first template**

Use this structure exactly as the new template body:

```markdown
---
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources:
  - "sources/FILENAME"
source_types:
  - "academic_paper | technical_article | code_repository | book | note | documentation | other"
tags:
  - "TAG"
status: "draft"  # draft | active | archived
---

# PageTitle

一句话定义或概括。——[[RelatedConcept]]

## 知识卡片

### 核心问题

这个页面要解决或解释的根本问题是什么？

### 核心洞察

从来源材料中沉淀出的可复用知识是什么？

### 机制/模型

如果可以抽象，给出机制、流程、公式或 mental model。

### 适用边界

这个知识在什么条件下成立？什么时候不适用？

### 与已有知识的关系

它扩展、修正、反驳或实例化了哪些已有页面？

## 来源笔记

<!-- 根据 source_types 从 assets/source_snippets.md 插入对应片段。只保留能从来源可靠提取的字段，不为填满模板而编造内容。 -->

## 相关页面

- [[RelatedPage]] — 关系描述

## 来源

- [来源名称](../sources/FILENAME)

## 变更日志

- YYYY-MM-DD: 初始创建
```

- [ ] **Step 2: Review the edited template**

Run: `git diff -- assets/page_template.md`
Expected: the template no longer assumes academic papers as the default page structure.

### Task 2: Add source snippet library

**Files:**
- Create: `assets/source_snippets.md`

- [ ] **Step 1: Create the snippet library**

Create `assets/source_snippets.md` with sections for `academic_paper`, `academic_paper_deep`, `technical_article`, `code_repository`, `note`, `documentation`, `book`, and `other`.

- [ ] **Step 2: Include the paper-parse strengths without making them mandatory**

Move the useful paper-oriented ideas into `academic_paper` and `academic_paper_deep`: structured summary, four elements, evidence/limitations, optional deep sections for introduction/method/results/discussion/conclusion.

- [ ] **Step 3: Review the new file**

Run: `git diff -- assets/source_snippets.md`
Expected: snippets are source-note fragments, not complete page templates.

### Task 3: Update ingest rules

**Files:**
- Modify: `assets/ingest_rules.md`

- [ ] **Step 1: Add the three-stage decision flow**

Add rules stating agents must decide in this order:
1. target knowledge page;
2. source type and snippet;
3. detail depth.

- [ ] **Step 2: Add the no-fabrication rule for template fields**

State that agents should omit fields that cannot be reliably extracted instead of writing generic filler.

- [ ] **Step 3: Clarify deep paper mode triggers**

Deep paper structure is used only when the user asks for deep paper analysis, the paper is the core source, or the paper underpins multiple concept pages.

- [ ] **Step 4: Review the edited rules**

Run: `git diff -- assets/ingest_rules.md`
Expected: rules match the one-master-template plus source-snippet model.

### Task 4: Verify with project tools

**Files:**
- Read/execute: `scripts/agent-bridge.py`

- [ ] **Step 1: Run environment check**

Run: `.venv/Scripts/python.exe scripts/agent-bridge.py check` if `.venv/Scripts/python.exe` exists, otherwise `python scripts/agent-bridge.py check`.
Expected: structured report or actionable failure.

- [ ] **Step 2: Run lint/status if check succeeds**

Run: `.venv/Scripts/python.exe scripts/agent-bridge.py lint` if the environment check succeeds.
Expected: no new dead links caused by asset changes.

### Task 5: Test template against a recent Meta recommender-systems paper

**Files:**
- Use network tools to locate a Meta recommender-system paper from the last three months.
- Do not write generated content into `sources/`.
- Optionally create and then remove a temporary `wiki/TemplateTestMetaRecommender.md` if needed.

- [ ] **Step 1: Locate a suitable paper**

Search web for recent Meta recommender systems papers within the last three months.
Expected: a real Meta paper with title, authors or venue, and accessible abstract/PDF page.

- [ ] **Step 2: Map it to the new template**

Draft a short sample mapping in the conversation or temporary file showing:
- knowledge card sections;
- `academic_paper` source note;
- whether `academic_paper_deep` is warranted.

- [ ] **Step 3: Validate outcome**

Confirm the sample does not require a separate source page and does not force paper-only fields into the main page skeleton.

### Task 6: Final review

**Files:**
- Review git diff for all changed files.

- [ ] **Step 1: Run final diff review**

Run: `git diff -- assets/page_template.md assets/source_snippets.md assets/ingest_rules.md docs/superpowers/plans/2026-05-13-source-snippet-template.md`
Expected: changes are limited to the approved template/rules/plan work.

- [ ] **Step 2: Report completion**

Summarize changed files, verification commands, and Meta paper template-test result.

## Self-Review

- Spec coverage: The plan covers the approved option B, the single physical page constraint, the source snippet library, ingest-rule updates, and the Meta paper test.
- Placeholder scan: No TBD/TODO placeholders are used as implementation instructions.
- Type consistency: Source type names are consistent across the plan and proposed frontmatter.
