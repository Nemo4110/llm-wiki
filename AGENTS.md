# Agent 使用指南

> 本文件指导 Claude Code、OpenClaw 等 AI Agent 如何使用 llm-wiki。

## Sources 目录写入规则

> `sources/` 的完整性是整个知识库的根基。一旦原始资料被污染，所有派生的 wiki 内容都将失去可信度。

### 允许写入 `sources/` 的两种情况

| 情况 | 条件 | 操作 |
|------|------|------|
| A | 用户手动放入文件 | 只读，不修改 |
| B | 用户提供了 URL/DOI，文件尚未在 `sources/` 中 | 使用网络工具获取，验证内容非空且格式正确后写入 |

### 绝对禁止

- **禁止**将 LLM 生成的文本、摘要、推测内容保存为 `.md`、`.txt` 或任何格式放入 `sources/`
- **禁止**在没有实际执行网络请求的情况下，声称"已下载"并创建文件
- **禁止**在获取失败时用生成内容"兜底"

### 标准网络获取模板

**直接下载（PDF、文本文件）**：

```bash
# 检查 URL 是否可达
curl -I -L "https://example.com/paper.pdf"

# 下载到 sources/
curl -L -o "sources/YYYY-MM-DD-描述.pdf" "https://example.com/paper.pdf"

# 验证文件非空
ls -la "sources/YYYY-MM-DD-描述.pdf"
```

**需要渲染的网页（技术博客、动态内容）**：

使用 Playwright 工具获取页面内容：

```bash
# 使用 playwright 获取渲染后的页面
playwright screenshot --full-page "https://tech.blog.example.com/article" "sources/temp-screenshot.png"
```

或使用 Python 脚本获取文本：

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://tech.blog.example.com/article")
    text = page.inner_text("article")  # 或合适的 selector
    with open("sources/YYYY-MM-DD-描述.md", "w", encoding="utf-8") as f:
        f.write(text)
    browser.close()
```

**DOI 解析**：

```bash
# DOI 通常重定向到出版商页面，可能需要处理付费墙
curl -L -o "sources/paper.html" "https://doi.org/10.xxxx/xxxxx"

# 优先尝试 arXiv 等开放获取版本
curl -L -o "sources/paper.pdf" "https://arxiv.org/pdf/xxxxx.pdf"
```

### 获取失败处理流程

```
获取尝试
    |
    +-- 成功 → 验证文件非空 → 写入 sources/ → 继续 ingest
    |
    +-- 失败（404/403/付费墙/反爬）
          |
          +--> 不在 sources/ 创建任何文件
          +--> 在 wiki/ 创建或更新 [[Pending: 来源名]] stub 页面
          +--> 在 log.md 记录失败原因
          +--> 回复用户说明情况，请求协助
```

### 正确 vs 错误示例

**错误**（绝对禁止）：

```
用户：请摄入这些论文 [提供 5 个标题，无 URL]

Agent：（没有执行任何 curl/playwright 调用）
      直接创建 sources/paper-1.md，内容为 LLM 生成的"摘要"
      然后基于这些伪造内容创建 wiki 页面
```

**正确**（无 URL，Agent 主动搜索）：

```
用户：请摄入这些论文 [提供 5 个标题，无 URL]

Agent：使用 WebSearch 搜索每个标题的开放获取版本
      → 找到论文 1 的 arXiv 链接、论文 2 的作者主页 PDF
      回复用户："我搜索到了以下可能来源，请确认是否正确：
      1. 《论文标题1》→ https://arxiv.org/pdf/xxxx.pdf
      2. 《论文标题2》→ https://author-page.edu/paper2.pdf
      确认后我将下载并执行 ingest。"
      （用户确认后 → 执行 curl 下载 → 继续 ingest）
```

**正确**（有 URL 的情况）：

```
用户：请摄入 https://arxiv.org/pdf/2401.xxxxx.pdf

Agent：执行 curl -L -o "sources/2026-04-20-paper.pdf" "https://arxiv.org/pdf/2401.xxxxx.pdf"
      验证文件大小 > 0
      读取 PDF 内容
      继续正常 ingest 流程
```

**正确**（获取失败的情况）：

```
用户：请摄入 https://example.com/paywalled-paper.pdf

Agent：执行 curl -I "https://example.com/paywalled-paper.pdf"
      → 返回 403 Forbidden
      不创建 sources/ 文件
      创建 wiki/Pending-Paywalled-Paper.md（stub，标记为待获取）
      记录 log.md："[日期] pending | 付费墙阻止获取 xxx"
      回复用户："该论文需要付费访问，我无法自动获取。
      请手动下载后放入 sources/，或提供开放获取版本链接。"
```

## 文件类型处理策略

> **关键原则**：不同文件类型需要不同的读取策略，避免直接使用 Read 工具处理二进制文件。

### 决策树

```
File Type Recognition
    |
    +-- Text files (.md, .txt, .json, .yaml, .py, .js, etc.)
    |     +--> Use Read tool directly
    |
    +-- PDF files (.pdf)
    |     +-- Check dependency: is PyMuPDF (pymupdf) installed?
    |     |     +-- Yes -> Use Python script to read
    |     |     +-- No  -> Install dependency first, then read
    |     +--> Process via scripts/read_pdf.py or Python code
    |
    +-- Image files (.png, .jpg, .jpeg, .gif, etc.)
    |     +--> Use Read tool (vision model supported)
    |
    +-- Office documents (.docx, .xlsx, .pptx)
    |     +--> Requires python-docx / openpyxl, etc.
    |
    +-- Other binary formats
          +--> Find or create corresponding Python processing script
```

### PDF 文件处理详细流程

**步骤 1：检查依赖**

```bash
# 检查 PyMuPDF 是否已安装
python -c "import fitz; print(fitz.__doc__[:30])"
```

如果失败，需要先安装：

```bash
pip install pymupdf>=1.25.0
```

**步骤 2：读取 PDF 内容**

**方法 A：使用现有脚本**

```bash
# 读取全部页面
python scripts/read_pdf.py sources/paper.pdf

# 读取指定页面范围
python scripts/read_pdf.py sources/paper.pdf 1-10
```

**方法 B：使用 Python 代码（推荐：PyMuPDF）**

```python
import fitz  # PyMuPDF

doc = fitz.open("sources/paper.pdf")
for page in doc:
    print(page.get_text())
doc.close()
```

**回退方案：pdfplumber（表格提取）**

如果 PyMuPDF 在提取复杂表格时效果不佳，可回退使用 `pdfplumber`（注意需安装安全版本 >= 0.11.8 以修复 CVE-2025-64512）：

```python
import pdfplumber

with pdfplumber.open("sources/paper.pdf") as pdf:
    for page in pdf.pages:
        print(page.extract_text())
```

**OCR 最后手段**

对于扫描版 PDF 或上述方法均失败的情况，可使用 `pdf2image` + `pytesseract` 进行 OCR。

**PDF 提取质量不佳时的回退方案**

如果 pdfplumber 提取的文本出现大量乱码（尤其是包含中文、特殊字体或复杂排版的学术论文），可尝试以下替代方案：

**方法 C：使用 PyMuPDF（fitz）**

PyMuPDF 对 CJK（中日韩）字体和复杂 PDF 的文本提取通常更可靠：

```bash
# 安装
pip install pymupdf
```

```python
import fitz  # PyMuPDF

doc = fitz.open("sources/paper.pdf")
for page in doc:
    print(page.get_text())
```

**方法 D：转换为图片后 OCR（最后手段）**

对于扫描版 PDF 或上述方法均失败的情况，可使用 `pdf2image` + `pytesseract` 进行 OCR，但速度较慢。

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
- `pymupdf>=1.25.0` - PDF 处理（PyMuPDF，支持 CJK 字体和复杂排版）

**回退依赖**（仅在 PyMuPDF 提取表格效果不佳时使用）：
- `pdfplumber>=0.11.8` - PDF 表格提取（需安全版本修复 CVE-2025-64512）
- `pdfminer.six>=20251107` - PDF 底层库

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
   - **Ingest 时必须创建 stub 页面**：任何新页面中首次出现的 `[[Concept]]`，如果目标页面不存在，必须同步创建一个 stub（至少包含 frontmatter + 一句话定义）
   - **双向链接检查**：更新现有页面后，检查是否有新页面应该反向链接过来

**不需要**：调用任何 CLI 命令

### 模式 B：CLI 模式

**适用场景**：用户明确要求使用命令行工具，或需要脚本化操作

**你的行为**：
1. 检查 CLI 是否可用：`python -m src.llm_wiki --help`
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
python -c "from src.llm_wiki.core import WikiManager; print('OK')"

# 命令行入口
# python -m src.llm_wiki --help
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
User Input
    |
    +-- Natural language ("ingest sources", "query wiki")
    |     +--> Protocol mode: operate files directly
    |
    +-- Explicit CLI ("run wiki lint", "check status")
    |     +--> CLI mode: execute commands and explain output
    |
    +-- Scripting needs ("batch process", "automation")
          +--> CLI mode: generate / execute scripts
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
3. 创建 wiki/Attention-Mechanism.md（内含 [[Self-Attention]]、[[Transformer]] 等链接）
4. 检查死链：创建 wiki/Self-Attention.md 和 wiki/Transformer.md 等 stub 页面
5. 更新 wiki/index.md
6. 追加 log.md

回复：已摄入 paper.pdf，创建了 [[Attention Mechanism]] 页面，并同步创建了 [[Self-Attention]]、[[Transformer]] 等关联概念 stub...
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
    .venv/Scripts/python -c "from src.llm_wiki.core import ..."
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

## 双向更新实现指南

> 本章节指导 Agent 如何在 ingest 过程中执行动态关联和反向更新。

### 为什么需要双向更新

传统 ingest 只创建新页面，已有页面不会自动反映新知识。双向更新让知识库随时间**自我完善**：
- 新论文改进了旧方法 → 旧页面自动补充"最新进展"
- 新工作与旧工作形成对比 → 双方页面添加对比链接
- 新工作依赖旧概念 → 旧概念页面获得反向引用

### 关联工作流

```
Finish new page creation
    |
    v
+----------------------------------+
| 1. Run: wiki link --source PAGE  |  <-- CLI discovers relations
|         --mode light             |
+----------------------------------+
    |
    v
+----------------------------------+
| 2. Agent reviews relation report |  <-- LLM judges relevance
|    Only process score >= 0.5     |
+----------------------------------+
    |
    v
+----------------------------------+
| 3. For each high-confidence rel: |
|    a. Read existing page         |
|    b. Analyze old vs new         |
|    c. Choose merge strategy      |
|    d. Run: wiki link --target    |
|    e. Review diff, then apply    |
+----------------------------------+
    |
    v
Update log.md, record operations
```

### 合并策略选择决策树

```
Relation between new page and existing page
    |
    +-- Same field, different work
    |     +--> link_only (add to "Related Pages")
    |
    +-- New work extends/improves old method
    |     +--> append_section (add "Latest Progress")
    |
    +-- New work contrasts with old work
    |     +--> append_section (add "Comparison with xxx")
    |     +--> append_related (bidirectional links)
    |
    +-- New work corrects old concept
    |     +--> update_concept (update definition, use with care)
    |     +--> append_section (add "Concept Evolution")
    |
    +-- New work heavily depends on old concept
          +--> append_related (add backlink to old page)
```

### CLI 命令参考

**发现关联（轻量模式）：**
```bash
python -m src.llm_wiki link --source "Bid2X" --mode light
```
输出：Markdown 关联报告，包含相关页面、score、关系类型、建议操作

**发现关联（深度模式，含 embedding）：**
```bash
python -m src.llm_wiki link --source "Bid2X" --mode deep --max-related 10
```

**执行具体合并（带 diff 审查）：**
```bash
# 预览
python -m src.llm_wiki link --source "Bid2X" --target "RTBAgent" \
    --strategy append_related --dry-run

# 应用
python -m src.llm_wiki link --source "Bid2X" --target "RTBAgent" \
    --strategy append_related
```

**批量全局关联：**
```bash
# 对最近 7 天新增页面做全局深度关联
python -m src.llm_wiki relink --mode deep --dry-run

# 指定日期范围
python -m src.llm_wiki relink --since 2026-04-20 --mode deep
```

### Agent 实现模式（协议模式）

**场景：用户要求摄入 sources/new-paper.pdf**

```
Agent:
1. 读取 sources/new-paper.pdf
2. 提取洞察，创建 wiki/NewMethod.md
3. 检查死链，创建 stub 页面
4. 运行 CLI（如有虚拟环境）：
   .venv/Scripts/python -m src.llm_wiki link --source "NewMethod" --mode light
   → 获得关联报告
5. 对 score >= 0.5 的关联，如 [[OldMethod]]：
   a. 读取 wiki/OldMethod.md
   b. LLM 分析："NewMethod 是对 OldMethod 的改进，扩展了 xxx 能力"
   c. 决策：使用 append_section 策略，追加"与 NewMethod 的关系"
   d. 运行 CLI 生成 diff：
      .venv/Scripts/python -m src.llm_wiki link \
        --source "NewMethod" --target "OldMethod" \
        --strategy append_section --dry-run
   e. 审查 diff，确认合理
   f. 应用修改（去掉 --dry-run）
6. 更新 log.md，记录新增页面和关联更新
7. 更新 wiki/index.md
```

### 安全守则

1. **永远先 --dry-run**：生成 diff 审查后再应用
2. **只追加不替换**：`append_related` 和 `append_section` 是安全策略
3. **谨慎使用 update_concept**：只有在确认新信息确实修正了旧定义时才使用
4. **限制批量更新**：单次 source 触发的反向更新不超过 5 个页面
5. **备份自动**：CLI 工具会自动备份到 `wiki/.backups/`，可回滚

### 故障处理

| 问题 | 解决 |
|------|------|
| `wiki link` 报错找不到页面 | 确认页面已创建，检查标题拼写 |
| diff 不合理 | 不应用，改为手动编辑页面 |
| 误关联到不相关页面 | 忽略（score 通常 < 0.3），不执行合并 |
| 策略不在允许列表 | 检查 config.yaml 的 `linking.deep_mode.strategies_allowed` |
| 备份目录过大 | 手动清理 `wiki/.backups/` 中的旧备份 |

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

*Agent 指南版本：1.2.0*
*最后更新：2026-04-20*
