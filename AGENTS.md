# Agent 使用指南

> 本文件指导 Claude Code、OpenClaw 等 AI Agent 如何使用 llm-wiki。

## 你有两种工作模式

### 模式 A：协议模式（推荐）

**适用场景**：用户用自然语言指令，如"请摄入资料"、"查询 wiki"

**你的行为**：
1. 阅读 `CLAUDE.md` 了解协议
2. 直接操作文件（读取、写入、编辑）
3. 按照 Ingest/Query/Lint 工作流执行

**不需要**：调用任何 CLI 命令

### 模式 B：CLI 模式

**适用场景**：用户明确要求使用命令行工具，或需要脚本化操作

**你的行为**：
1. 检查 CLI 是否可用：`python -m skills.llm_wiki --help`
2. 使用相应命令辅助执行

## CLI 工具参考

### 检查 CLI 可用性

```bash
# 检查是否能导入
python -c "from skills.llm_wiki.core import WikiManager; print('OK')"

# 或使用命令行
python -m skills.llm_wiki --help
```

### 可用命令

| 命令 | 用途 | 示例 |
|-----|------|------|
| `wiki status` | 查看 wiki 概览 | 快速了解页面数量、最近活动 |
| `wiki lint` | 健康检查 | 发现孤儿页面、死链等问题 |
| `wiki ingest <path>` | 摄取资料（辅助）| 验证资料存在，预览影响 |

**注意**：`wiki ingest` 和 `wiki query` 需要 LLM 处理，CLI 只提供辅助功能。实际 ingest/query 建议用**协议模式**直接操作文件。

### CLI 辅助工作流示例

```bash
# 1. 先检查 wiki 状态
python -m skills.llm_wiki status

# 2. 发现资料有问题，运行 lint
python -m skills.llm_wiki lint

# 3. 用户要求摄入新资料，你（Agent）直接处理：
#    - 读取 sources/new-paper.pdf
#    - 提取洞察
#    - 更新 wiki/ 下的页面
#    - 追加 log.md
```

## 决策树

```
用户输入
    │
    ├─ 自然语言（"摄入资料"、"查询 wiki"）
    │     └─▶ 协议模式：直接操作文件
    │
    ├─ 明确 CLI（"运行 wiki lint"、"检查状态"）
    │     └─▶ CLI 模式：执行命令并解释输出
    │
    └─ 脚本化需求（"批量处理"、"自动化"）
          └─▶ CLI 模式：生成/执行脚本
```

## 重要原则

1. **默认用协议模式**：大多数用户期望自然语言交互
2. **CLI 是补充**：用于状态查看、批量操作、脚本集成
3. **不要假设 CLI 已安装**：用户可能没装依赖，优先用纯文件操作
4. **保持透明**：如果使用了 CLI，告诉用户你在做什么

## 示例对话

### 场景 1：自然语言指令

```
用户：请摄入 sources/paper.pdf

你（协议模式）：
1. 读取 sources/paper.pdf
2. 提取关键洞察
3. 创建 wiki/Attention-Mechanism.md
4. 更新 wiki/index.md
5. 追加 log.md

回复：已摄入 paper.pdf，创建了 [[Attention Mechanism]] 页面...
```

### 场景 2：明确 CLI 请求

```
用户：运行 wiki lint 看看有什么问题

你（CLI 模式）：
1. 执行：python -m skills.llm_wiki lint
2. 分析输出
3. 解释问题并提供修复建议

回复：发现 3 个孤儿页面：[[PageA]]、[[PageB]]...
```

### 场景 3：CLI 不可用

```
用户：运行 wiki status

你：尝试执行 python -m skills.llm_wiki status
    → 失败（ModuleNotFoundError）

你：切换到协议模式，直接读取文件
    - 读取 wiki/ 统计页面数量
    - 读取 log.md 获取最近活动

回复：wiki 目前有 15 个页面，最近活动是...
（注：CLI 工具未安装，我直接读取文件获取的信息）
```

## 技术细节

### CLI 入口点

- **模块**：`skills.llm_wiki`
- **主文件**：`skills/llm_wiki/commands.py`
- **核心逻辑**：`skills/llm_wiki/core.py`

### 依赖

CLI 需要：
- `click` - 命令行框架
- `pyyaml` - YAML 解析

检查方式：
```python
import importlib.util
spec = importlib.util.find_spec("click")
if spec is None:
    print("CLI 依赖未安装，使用协议模式")
```

### 与 CLAUDE.md 的关系

- `CLAUDE.md`：定义**用户可见**的工作协议
- `AGENTS.md`：定义**Agent 内部**的实现策略

两者不矛盾：协议模式实现 CLAUDE.md 的语义，CLI 模式提供额外的工具能力。

---

*Agent 指南版本：1.0.0*
*最后更新：2026-04-13*
