# LLM-Wiki Skill

[Karpathy 的 llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 的 Claude Code SKILL 实现。

> **核心理念**：LLM 是程序员，Wiki 是代码库，用户是产品经理。

## 为什么选择 SKILL 形式？

| 维度 | 独立应用 (如 [Sage-Wiki](https://github.com/xoai/sage-wiki)) | 本 SKILL 实现 |
|------|----------------------|--------------|
| 架构 | Go + SQLite + 嵌入式前端 | 纯 Markdown |
| 部署 | 需要运行服务 | 零部署 |
| 集成 | 通过 MCP 间接 | 原生命令 |
| 代码量 | ~10k 行 | ~500 行 |
| 数据格式 | 专有格式 | 纯文本 Markdown |
| 编辑器 | 锁定在应用内 | Obsidian/VSCode/任意 |

## 快速开始

### 1. 克隆/复制此项目

```bash
git clone https://github.com/yourname/llm-wiki.git
cd llm-wiki
```

### 2. 安装依赖（可选）

CLI 工具需要 Python 3.8+。根据你的工具选择安装方式：

#### 使用 uv（推荐，如果你有 uv）

```bash
# 创建虚拟环境并安装依赖
uv venv
uv pip install -r skills/requirements.txt --python .venv/Scripts/python.exe

# 激活环境（Windows）
.venv\Scripts\activate
# 或 Linux/macOS
source .venv/bin/activate
```

#### 使用 pip

```bash
# 创建虚拟环境
python -m venv .venv

# 激活环境
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# 安装依赖
pip install -r skills/requirements.txt
```

#### 验证安装

```bash
python -c "from skills.llm_wiki.core import WikiManager; print('✓ 安装成功')"
```

**纯协议模式**：如果你只想用 Claude Code 的自然语言指令（如"请摄入资料"），**不需要安装任何依赖**。直接跳到第 3 步。

### 3. 放入你的第一个资料

```bash
# 复制任何文件到 sources/
cp ~/Downloads/interesting-paper.pdf sources/
cp ~/Notes/ideas.md sources/
```

### 3. 让 Claude 开始工作

在 Claude Code 中：

```bash
请摄入 sources/interesting-paper.pdf 到 wiki
```

Claude 会：

1. 读取资料
2. 提取关键洞察
3. 创建/更新 wiki 页面
4. 建立交叉引用
5. 记录到 log.md

## 核心命令

### `/wiki-ingest <path>` — 摄取资料

```bash
/wiki-ingest sources/paper.pdf
/wiki-ingest sources/article.md
```

### `/wiki-query <question>` — 查询知识库

```bash
/wiki-query "Transformer 和 RNN 有什么区别？"
/wiki-query "我们讨论过哪些优化方法？"
```

### `/wiki-lint` — 健康检查

```bash
/wiki-lint
```

检查并报告：

- 孤儿页面（未被引用的页面）
- 死链（指向不存在的页面）
- 陈旧页面（90天未更新）
- 草稿页面

## 目录结构

```text
llm-wiki/
├── CLAUDE.md           # ⭐ 核心协议：Agent 的行为准则
├── AGENTS.md           # Agent 实现指南（CLI 使用说明）
├── README.md           # 本文件
├── log.md              # 时间线日志（追加式）
├── sources/            # 原始资料（用户管理，Agent 只读，默认不进 git）
│   └── README.md
├── wiki/               # 生成的知识页面（Agent 管理）
│   ├── index.md        # 入口索引
│   └── *.md            # 主题页面
├── schema/             # 配置和模板
│   ├── page_template.md
│   └── ingest_rules.md
├── skills/             # SKILL 实现（可选，用于 CLI）
│   └── llm_wiki/
└── examples/           # 示例 wiki
```

**关于 `sources/`**：默认被 `.gitignore` 排除，避免仓库臃肿。wiki 只保留提取的知识，原始文件由你另行管理（网盘、Zotero 等）。如需追踪特定文件，见 `sources/README.md`。

## 工作原理

### 数据流

```text
┌──────────┐     ┌─────────────┐     ┌──────────┐
│ sources/ │────▶│  LLM 处理   │────▶│  wiki/   │
│ (原始)   │     │ (提取+关联)  │     │ (结构化) │
└──────────┘     └─────────────┘     └──────────┘
                          │
                          ▼
                    ┌──────────┐
                    │ log.md   │
                    │ (记录)   │
                    └──────────┘
```

### 关键设计

1. **CLAUDE.md 作为协议**：定义了 Agent 的行为规范，任何人/任何 Agent 都可以遵循
2. **纯 Markdown**：无数据库，无锁定，git 原生支持版本控制
3. **双向链接**：`[[PageName]]` 格式，与 Obsidian 兼容
4. **累积式学习**：每次查询可以产生新的 wiki 页面，知识不断积累

## 查询机制详解

### 当前实现：符号导航 + LLM 综合

本 SKILL **不依赖 Embedding/向量检索**，查询通过以下步骤完成：

```text
用户提问
    │
    ▼
┌─────────────────┐
│ 1. 读取 index.md │ ← 人工/Agent 维护的分类索引
│    定位相关主题  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. 读取相关页面  │ ← 通过 [[链接]] 跳转发现关联
│    及其链接邻居  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. LLM 综合     │ ← 基于读取的内容生成回答
│    生成带引用    │      引用格式：[[页面名]]
└─────────────────┘
```

**示例流程**：

用户问："LoRA 是什么？"

1. **Agent 读取** `wiki/index.md`，在「AI/ML」主题下找到 `[[LoRA]]`
2. **Agent 读取** `wiki/LoRA.md`，发现链接到 `[[Fine-tuning]]`、`[[Adapter]]`
3. **Agent 综合** 回答：
   > LoRA（Low-Rank Adaptation）是一种参数高效微调方法——详见 [[LoRA]]。
   > 与传统的 [[Fine-tuning]] 相比，它只训练低秩矩阵...

### 为什么不用 Embedding？

| 考量 | 当前方案 | Embedding 方案 |
|-----|---------|---------------|
| **依赖** | 零外部依赖 | 需要 Embedding API 或本地模型 |
| **成本** | 无额外费用 | 按 token/请求计费 |
| **隐私** | 数据不上传 | 需发送内容到外部服务 |
| **精度** | 精确链接，可解释 | 近似相似，可能召回无关内容 |
| **规模** | 适合 0-500 页 | 大规模（1000+ 页）必需 |

**结论**：对于个人/小团队知识库，维护好 `index.md` 和页面链接，比引入 Embedding 更简单有效。

### 何时需要 Embedding？

当你的 wiki 出现以下情况时，考虑升级：

- [ ] 页面数量 > 500，人工索引难以维护
- [ ] 查询多为模糊语义（"那个关于优化的论文..."）
- [ ] 需要跨主题联想（用户没提关键词，但语义相关）

见 [ROADMAP.md](ROADMAP.md) 了解升级计划。

## 示例工作流

### 场景 1：研究新领域

```bash
# 第 1 天：放入资料
sources/
├── 2026-04-10-transformer-paper.pdf
└── 2026-04-10-lora-blog.md
```

```bash
用户：请摄入新资料
Claude：已处理 2 个资料
  - 创建 [[Transformer]] — 注意力机制架构
  - 创建 [[LoRA]] — 低秩适配
  - 创建 [[Self-Attention]] — 自注意力详解
  - 更新 wiki/index.md
```

### 场景 2：深入探索

```bash
用户：LoRA 和全量微调有什么区别？

Claude（读取 wiki/index.md → 找到 [[LoRA]] → 综合回答）：

根据我们的 wiki：

**LoRA** —— [[LoRA]]
- 冻结预训练权重，只训练低秩矩阵
- 参数量减少 ~10000 倍

**全量微调**
- 更新所有参数
- 计算成本高

关键区别：
1. 参数量：LoRA 只训练 0.1%~1% 的参数 [[参数效率]]
2. 存储：LoRA 只保存适配器，不保存完整模型
3. 组合：多个 LoRA 可以叠加 [[LoRA 组合]]

这个回答有帮助吗？需要我把它存档到 wiki 吗？
```

### 场景 3：知识积累

```bash
用户：是的，存档这个回答

Claude：已创建 [[LoRA vs Full Fine-tuning]]
- 从对话中提取了对比要点
- 链接到 [[LoRA]] 和 [[Fine-tuning]]
- 添加到 wiki/index.md 的「常见问题」
```

## 与 Obsidian 配合使用

1. 用 Obsidian 打开 `wiki/` 目录
2. 享受图谱视图、快速导航、美观渲染
3. Claude Code 负责维护，Obsidian 负责阅读和思考

## 进阶配置

### 自定义页面模板

编辑 `schema/page_template.md`：

```markdown
---
created: {{date}}
updated: {{date}}
sources:
{{sources}}
tags:
{{tags}}
---

# {{title}}

## TL;DR

一句话总结。

## 核心要点

{{insights}}

## 我的思考

（这里写你的原创思考）

## 相关

{{links}}
```

### 自定义 Ingest 规则

编辑 `schema/ingest_rules.md`，添加特定领域的处理逻辑。

## 对比其他方案

| 方案 | 特点 | 适用场景 |
|-----|------|---------|
| **本 SKILL** | 零依赖，纯文本，Claude Code 原生 | 个人知识管理，研究笔记 |
| Sage-Wiki | 功能完整，多模态，独立应用 | 团队知识库，企业部署 |
| Obsidian + 插件 | 可视化强，社区丰富 | 已有 Obsidian 工作流 |
| Notion/Logseq | 协作友好，实时同步 | 多人协作，移动访问 |

## 贡献

欢迎提交 Issue 和 PR！

详细路线图见 [ROADMAP.md](ROADMAP.md)。

### 当前 TODO

- [ ] MCP 服务器封装（让其他 Agent 也能用）
- [ ] Obsidian 插件（一键同步状态）
- [ ] 增量 embedding 加速检索
- [ ] 多语言支持

## 许可

MIT License — 自由使用，尽情改造。

---

*Inspired by [Karpathy's llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)*
