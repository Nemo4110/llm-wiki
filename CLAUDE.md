# LLM-Wiki 工作协议

> 这是 llm-wiki 的核心协议文件。作为 Agent，你必须遵循此协议维护知识库。

## 设计哲学

- **LLM 即程序员，Wiki 即代码库**
- **用户负责**：放入资料、提出好问题、判断意义
- **你负责**：摘要、交叉引用、索引、日志、所有繁琐工作
- **积累优于检索**：每次交互都应留下持久价值

## 目录结构

```text
llm-wiki/
├── sources/          # 原始资料（只读，用户管理）
│   └── README.md     # 资料管理指南
├── wiki/             # 生成的知识页面（你管理）
│   ├── index.md      # 入口索引
│   └── *.md          # 主题页面
├── assets/           # 模板和配置
│   ├── page_template.md
│   └── ingest_rules.md
├── scripts/          # 辅助脚本（可选）
├── src/              # CLI 实现（可选）
├── log.md            # 时间线日志（追加式）
├── CLAUDE.md         # 本文件
├── AGENTS.md         # Agent 实现指南
└── SKILL.md          # 技能规范
```

## 核心工作流

### 1. Ingest（摄取）

**触发**：用户添加资料到 `sources/`，或明确要求 `/wiki-ingest <path>`

**步骤**：

1. **读取**资料内容
2. **提取**关键洞察（insights）
3. **识别**受影响的 wiki 页面（新建或更新）
4. **更新**页面：合并新信息，保持原有结构
5. **维护**交叉引用：`[[PageName]]` 格式。创建新页面时出现的所有内部链接，若目标页面不存在，必须同时创建对应的 **stub 页面**（至少包含一句话定义 + 规范 frontmatter）。
6. **记录**到 `log.md`：

   ```markdown
   ## [2026-04-10] ingest | 资料名
   - 新增页面：[[PageA]], [[PageB]]
   - 更新页面：[[PageC]]
   - 关键洞察：一句话总结
   ```

7. **更新** `wiki/index.md`

**规则**：

- 一个概念一个页面
- 页面名使用 PascalCase（如 `Transformer.md`）
- 用 `[[链接]]` 建立关联，不重复内容

### 2. Query（查询）

**触发**：用户问 `/wiki-query <问题>` 或直接提问涉及知识库

**步骤**：

1. **读取** `wiki/index.md` 定位相关页面
2. **读取**相关 wiki 页面内容
3. **综合**回答，使用引用格式：`[[页面名]]`
4. **判断**：这个回答是否值得存档？
   - 如果是新洞察 → 创建新页面或追加到现有页面
   - 如果是常见问题 → 更新 `wiki/index.md` 的 FAQ 部分

### 3. Lint（健康检查）

**触发**：`/wiki-lint` 或定期执行

**检查项**：

- [ ] **孤儿页面**：没有被任何页面引用的页面
- [ ] **死链**：`[[不存在的页面]]`
- [ ] **陈旧页面**：超过 90 天未更新
- [ ] **矛盾声明**：同一概念在不同页面定义冲突
- [ ] **待办项**：`TODO` 标记未处理

**输出**：Markdown 报告，包含修复建议

## 页面格式规范

### Frontmatter（必须）

```yaml
---
created: 2026-04-10
updated: 2026-04-10
sources:
  - "sources/paper.pdf"
  - "sources/笔记.md"
tags:
  - "AI/ML"
  - "架构"
status: "active"  # active | draft | archived
---
```

### 页面结构

```markdown
# 页面标题

一句话定义。——[[相关概念]]

## 核心要点

- 要点 1
- 要点 2——见[[另一页面]]

## 详细说明

...

## 相关页面

- [[PageA]] — 关系描述
- [[PageB]] — 关系描述

## 来源

- [资料名](../sources/xxx)

## 变更日志

- 2026-04-10: 初始创建
```

## 交叉引用规则

1. **首次提及**概念时创建链接：`[[Concept]]`
2. **避免过度链接**：同一页面中多次提及，只链接第一次
3. **双向链接**：创建新页面时，检查哪些现有页面应该链接过来
4. **链接文本**：保持自然，可使用 `[[Target|显示文本]]`
5. **链接落地**：每个 `[[PageName]]` 都必须指向一个真实存在的页面。如果目标页面尚未创建，必须在本次 ingest 结束时同步创建 stub（至少包含 `# 标题`、一句话定义和 frontmatter）

## 索引格式（index.md）

```markdown
# Wiki Index

## 最近活动
<!-- 从 log.md 提取最近 5 条 -->

## 快速入口

### 按主题
- **AI/ML**: [[Transformer]], [[LoRA]], [[RLHF]]
- **系统**: [[架构]], [[性能]]

### 按状态
- 🟢 活跃: ...
- 🟡 草稿: ...
- 🔴 待整理: ...

## 待办
- [ ] [[Draft: 新概念]] — 需要完善
```

## 日志格式（log.md）

```markdown
# Wiki Log

## [2026-04-10] ingest | 论文：Attention Is All You Need
- 新增：[[Transformer]], [[Self-Attention]], [[Multi-Head Attention]]
- 更新：[[NLP 架构演进]]
- 关键洞察：Transformer 统一了编码器-解码器架构

## [2026-04-09] query | "Transformer 和 RNN 的区别"
- 回答已存档到 [[Transformer vs RNN]]
```

## 你的行为准则

### DO

- 主动维护：用户没要求时也指出问题
- 保持简洁：不要过度工程化
- 引用来源：每个声明都可追溯到 sources/
- 渐进完善：草稿页面好过没有页面

### DON'T

- 不要删除用户放入 sources/ 的原始资料
- 不要在没有确认的情况下大规模重构
- 不要创建没有链接的孤立页面
- 不要留下死链（`[[不存在的页面]]`）
- 不要在正文中重复 frontmatter 信息

## 相关文件

- `AGENTS.md` — 给 Claude Code / OpenClaw 等 Agent 的实现指南
  - CLI 工具使用说明
  - 协议模式 vs CLI 模式决策树
  - 故障处理参考

## 版本

Protocol: v1.1.0
Last Updated: 2026-04-16
