# Sources 目录

> 放入你想让 Wiki 吸收的所有原始资料。

## 支持的格式

- Markdown (.md)
- 文本文件 (.txt)
- PDF (.pdf) — **需要安装安全版本的 pdfplumber>=0.11.8 和 pdfminer.six>=20251107**
- 代码文件 (.py, .js, etc.)
- 图片 (.png, .jpg) — 需要 vision 能力
- 网页链接 (.url 或粘贴内容)

### PDF 处理注意事项

**安全要求**：
- 必须使用安全版本：pdfplumber >= 0.11.8，pdfminer.six >= 20251107
- **原因**：CVE-2025-64512 漏洞可导致任意代码执行
- **避免**：直接使用系统工具（如 pdftoppm）读取 PDF，这会触发依赖错误

**依赖安装**：

```bash
# 安装安全版本的 PDF 处理库
pip install pdfplumber>=0.11.8 pdfminer.six>=20251107
```

这些依赖已在 `src/requirements.txt` 中定义，安装项目依赖时会自动安装。

## 使用流程

1. **放入资料**：复制或下载文件到此目录
2. **告诉 Agent**：「请摄入新资料」或 `/wiki-ingest 文件名`
3. **Agent 处理**：
   - 读取内容
   - 提取要点
   - 更新 wiki 页面
   - 记录日志

## 文件命名建议

```
YYYY-MM-DD-描述.扩展名
# 例如：
2026-04-10-karpathy-llm-wiki-gist.md
2026-04-09-transformer-paper.pdf
```

## Git 管理说明

**默认情况下，`sources/` 中的文件不会被 Git 追踪**（已加入 `.gitignore`）。

原因：
- 原始资料通常很大（PDF、视频、归档文件）
- wiki 已经提取了关键信息到 `wiki/` 目录
- 原始文件可通过其他方式管理（网盘、Zotero、云存储）

### 如果你想追踪某些文件

编辑 `.gitignore`，添加例外规则：

```gitignore
# 追踪 Markdown 笔记
!sources/*.md

# 追踪特定重要文件
!sources/2026-04-10-key-paper.pdf
```

或使用 `git add -f` 强制添加：

```bash
git add -f sources/important-notes.md
```

## 使用注意

- 此目录只由**用户管理**（添加、删除、重命名）
- Agent **只读**，不会修改或删除这里的文件
- 大型文件建议先压缩或提取关键部分
