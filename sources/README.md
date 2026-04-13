# Sources 目录

> 放入你想让 Wiki 吸收的所有原始资料。

## 支持的格式

- Markdown (.md)
- 文本文件 (.txt)
- PDF (.pdf) — 需要 OCR 或文本提取
- 代码文件 (.py, .js, etc.)
- 图片 (.png, .jpg) — 需要 vision 能力
- 网页链接 (.url 或粘贴内容)

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

## 注意

- 此目录只由**用户管理**（添加、删除、重命名）
- Agent **只读**，不会修改或删除这里的文件
- 大型文件建议先压缩或提取关键部分
