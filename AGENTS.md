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

### 检查依赖和虚拟环境

项目可能已安装虚拟环境，优先检查：

```bash
# 检查项目目录是否有虚拟环境
ls -la .venv/  # 或 venv/

# 如果有，使用虚拟环境的 Python
.venv/Scripts/python -c "from src.llm_wiki.core import WikiManager; print('OK')"  # Windows
.venv/bin/python -c "from src.llm_wiki.core import WikiManager; print('OK')"      # Linux/macOS
```

### 检查 CLI 可用性

```bash
# 使用虚拟环境的 Python（优先）
.venv/Scripts/python -c "from src.llm_wiki.core import WikiManager; print('OK')"

# 或使用系统 Python
python -c "from skills.llm_wiki.core import WikiManager; print('OK')"

# 命令行入口（暂未实现 __main__，推荐用协议模式）
# python -m skills.llm_wiki --help
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
# 使用虚拟环境（推荐）
PY=".venv/Scripts/python"  # Windows
PY=".venv/bin/python"      # Linux/macOS

# 1. 先检查 wiki 状态
$PY -c "from src.llm_wiki.core import WikiManager; from pathlib import Path; w = WikiManager(Path('wiki')); print(f'Pages: {len(w.list_pages())}')"

# 2. 运行 lint 检查问题
$PY -c "from src.llm_wiki.core import WikiManager, find_wiki_root; w = WikiManager(find_wiki_root()/'wiki'); print(w.lint())"

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

### 场景 3：使用虚拟环境

```
用户：检查 wiki 状态

你：发现项目有 .venv/ 目录，使用虚拟环境
    .venv/Scripts/python -c "from skills.llm_wiki.core import ..."
    → 成功获取信息

回复：wiki 目前有 15 个页面，最近活动是...
```

### 场景 4：使用 conda 环境

```
用户：检查 wiki 状态

你：检测到 CONDA_PREFIX 环境变量，使用 conda 环境
    $CONDA_PREFIX/bin/python -c "from src.llm_wiki.core import ..."
    → 成功获取信息

回复：wiki 目前有 15 个页面，最近活动是...
（使用 conda 环境：llm-wiki）
```

### 场景 5：CLI 依赖未安装（协议模式降级）

```
用户：运行 wiki lint

你：尝试执行
    .venv/Scripts/python -c "from src.llm_wiki.core import WikiManager"
    → 失败（ModuleNotFoundError: .venv 不存在或未安装依赖）

你：切换到协议模式，直接读取文件
    - 读取 wiki/ 统计页面数量
    - 读取 log.md 获取最近活动
    - 手动执行 lint 逻辑

回复：wiki 目前有 15 个页面，发现 3 个孤儿页面：[[PageA]]...
（注：CLI 依赖未安装，我直接读取文件获取的信息）
```

## 技术细节

### CLI 入口点

- **模块**：`src.llm_wiki`
- **主文件**：`src/llm_wiki/commands.py`
- **核心逻辑**：`src/llm_wiki/core.py`

### 依赖和虚拟环境

依赖文件：`src/requirements.txt`
- `click` - 命令行框架
- `pyyaml` - YAML 解析

#### 检查依赖（含虚拟环境检测）

```python
import importlib.util
from pathlib import Path
import subprocess
import sys

# 1. 检测虚拟环境（uv/venv 或 conda）
venv_paths = [
    Path(".venv"),           # uv / modern tools
    Path("venv"),            # traditional
]
# 检测 conda 环境
conda_env = Path(os.environ.get("CONDA_PREFIX", ""))
if conda_env.exists():
    venv_python = conda_env / "python.exe" if sys.platform == "win32" else conda_env / "bin" / "python"
else:
    for venv in venv_paths:
venv_python = None
for venv in venv_paths:
    if venv.exists():
        venv_python = venv / "Scripts" / "python.exe" if sys.platform == "win32" else venv / "bin" / "python"
        break

# 决策路径
if venv_python and check_dep("src.llm_wiki", venv_python):
    print(f"使用虚拟环境: {venv_python}")
    python_cmd = str(venv_python)
elif check_dep("src.llm_wiki"):
    print("使用系统 Python")
    python_cmd = "python"
else:
    print("依赖未安装，使用协议模式")

# 2. 检查依赖是否可用
def check_dep(module_name, python_path=None):
    py = python_path or sys.executable
    result = subprocess.run([py, "-c", f"import {module_name}"], capture_output=True)
    return result.returncode == 0
```

### 与 CLAUDE.md 的关系

- `CLAUDE.md`：定义**用户可见**的工作协议
- `AGENTS.md`：定义**Agent 内部**的实现策略

两者不矛盾：协议模式实现 CLAUDE.md 的语义，CLI 模式提供额外的工具能力。

---

*Agent 指南版本：1.0.0*
*最后更新：2026-04-13*
