# Agent 使用指南

> 本文件指导 Claude Code、OpenClaw 等 AI Agent 如何使用 llm-wiki。

## 文件类型处理策略

> **关键原则**：不同文件类型需要不同的读取策略，避免直接使用 Read 工具处理二进制文件。

### 决策树

```
文件类型识别
    │
    ├─ 文本文件 (.md, .txt, .json, .yaml, .py, .js 等)
    │     └─▶ 直接使用 Read 工具读取
    │
    ├─ PDF 文件 (.pdf)
    │     ├─ 检查依赖：pdfplumber>=0.11.8 是否安装？
    │     │     ├─ 已安装 → 使用 Python 脚本读取
    │     │     └─ 未安装 → 先安装依赖，再读取
    │     └─▶ 通过 scripts/read_pdf.py 或 Python 代码处理
    │
    ├─ 图片文件 (.png, .jpg, .jpeg, .gif 等)
    │     └─▶ 使用 Read 工具（支持视觉模型）
    │
    ├─ Office 文档 (.docx, .xlsx, .pptx)
    │     └─▶ 需要安装 python-docx/openpyxl 等库
    │
    └─ 其他二进制格式
          └─▶ 查找或创建相应的 Python 处理脚本
```

### PDF 文件处理详细流程

**步骤 1：检查依赖**

```bash
# 检查 pdfplumber 是否已安装
python -c "import pdfplumber; print(pdfplumber.__version__)"
```

如果失败，需要先安装：

```bash
# 安全版本（已修复 CVE-2025-64512）
pip install pdfplumber>=0.11.8 pdfminer.six>=20251107
```

**步骤 2：读取 PDF 内容**

**方法 A：使用现有脚本**

```bash
# 读取全部页面
python scripts/read_pdf.py sources/paper.pdf

# 读取指定页面范围
python scripts/read_pdf.py sources/paper.pdf 1-10
```

**方法 B：使用 Python 代码**

```python
import pdfplumber

with pdfplumber.open("sources/paper.pdf") as pdf:
    # 读取第 1-10 页
    for i in range(min(10, len(pdf.pages))):
        page = pdf.pages[i]
        text = page.extract_text()
        print(f"Page {i+1}:\n{text}\n")
```

**重要安全提示**：
- **必须使用安全版本**：pdfplumber >= 0.11.8，pdfminer.six >= 20251107
- **原因**：CVE-2025-64512 漏洞可导致任意代码执行
- **避免**：直接使用 Read 工具读取 PDF（会触发 pdftoppm 依赖错误）

### 文本文件处理

直接使用 Read 工具：

```python
# 直接读取 Markdown、文本、代码文件
Read("sources/notes.md")
Read("sources/config.yaml")
Read("sources/script.py")
```

### 图片文件处理

Read 工具支持视觉模型：

```python
# Read 工具可以处理图片并返回视觉内容
Read("sources/diagram.png")
Read("sources/screenshot.jpg")
```

### 依赖管理

**依赖文件位置**：`src/requirements.txt`

**包含的依赖**：
- `click>=8.0.0` - CLI 框架
- `pyyaml>=6.0` - YAML 解析
- `pdfplumber>=0.11.8` - PDF 处理（安全版本）
- `pdfminer.six>=20251107` - PDF 处理底层库（安全版本）

**安装命令**：

```bash
# 使用 conda（推荐）
conda activate llm-wiki
pip install -r src/requirements.txt

# 使用 pip
pip install -r src/requirements.txt

# 使用 uv（如果你有）
uv pip install -r src/requirements.txt
```

---

## 你有两种工作模式

### 模式 A：协议模式（推荐）

**适用场景**：用户用自然语言指令，如"请摄入资料"、"查询 wiki"

**你的行为**：
1. 阅读 `CLAUDE.md` 了解协议
2. **根据文件类型选择正确的读取策略**（见上方"文件类型处理策略"）
3. 直接操作文件（读取、写入、编辑）
4. 按照 Ingest/Query/Lint 工作流执行

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
.venv/Scripts/python -m src.llm_wiki --help  # Windows
.venv/bin/python -m src.llm_wiki --help      # Linux/macOS
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

```bash
# 查看 wiki 状态
python -m src.llm_wiki status

# 健康检查
python -m src.llm_wiki lint

# 查看所有命令帮助
python -m src.llm_wiki --help
```

| 命令 | 用途 | 说明 |
|-----|------|------|
| `status` | 查看 wiki 概览 | 页面数量、最近活动 |
| `lint` | 健康检查 | 孤儿页面、死链等问题 |
| `ingest <path>` | 摄取资料（辅助）| 仅预览，实际处理需用协议模式 |
| `query <text>` | 查询 wiki（辅助）| 仅列出页面，实际查询需用协议模式 |

**注意**：`ingest` 和 `query` 需要 LLM 处理，CLI 只提供辅助功能。实际内容处理建议用**协议模式**直接操作文件。

### CLI 辅助工作流示例

```bash
# 使用虚拟环境（推荐）
PY=".venv/Scripts/python"  # Windows
PY=".venv/bin/python"      # Linux/macOS

# 1. 先检查 wiki 状态
$PY -m src.llm_wiki status

# 2. 运行 lint 检查问题
$PY -m src.llm_wiki lint

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
1. 执行：python -m src.llm_wiki lint
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

### 辅助脚本

项目包含辅助脚本（`scripts/`）：
- `scripts/wiki-status.sh` — 快速查看 wiki 状态
- `scripts/wiki-lint.sh` — 运行健康检查
- `scripts/init-wiki.sh` — 初始化新项目

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
