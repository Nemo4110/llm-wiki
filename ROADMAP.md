# LLM-Wiki 路线图

> 项目演进计划和待办事项

## 当前状态：v1.1.0

**核心功能**：
- [x] 基于协议的 wiki 工作流
- [x] Ingest / Query / Lint 三大命令
- [x] 纯 Markdown，零外部强制依赖
- [x] Obsidian 兼容
- [x] 可选 Embedding 混合检索（Ollama / OpenAI / MCP）

**查询机制**：默认使用符号导航 + LLM 综合；CLI 可选开启 Embedding 增强

---

## 短期计划（1-2 个月）

### 核心体验优化

- [ ] **增量 Ingest**：只处理新增/修改的资料，避免重复读取
- [ ] **Lint 自动修复**：`--fix` 参数自动处理孤儿页面、死链
- [ ] **查询结果存档**：一键将回答保存为 wiki 页面
- [ ] **搜索历史**：记录常见查询，自动提示

### 模板和示例

- [ ] 领域模板包：
  - [ ] 学术研究模板
  - [ ] 技术研究模板
  - [ ] 读书笔记模板
- [ ] 5 个完整示例 wiki

---

## 中期计划（3-6 个月）

### 检索增强（可选升级）

当 wiki 规模超过 ~500 页时，提供 Embedding 支持：

**方案：混合检索**

```
User Query
    |
    +--> Keyword Match  --> Title/Tag match (fast filter)
    |
    +--> Vector Search  --> Semantic similar pages (Embedding)
    |
    +--> Link Traversal --> Related pages (from hit pages)
                |
                v
        Merge + Deduplicate + Rank
                |
                v
        Top-K pages -> LLM Synthesis
```

**实现选项**：

| 方案 | 技术 | 优先级 |
|-----|------|--------|
| 本地轻量 | `sentence-transformers/all-MiniLM-L6-v2` | P1 |
| MCP 远程 | 通过 MCP 调用 OpenAI/Anthropic Embedding | P2 |
| 本地 heavy | `BAAI/bge-large-zh` 等高质量模型 | P3 |

**交付物**：

- [x] `src/llm_wiki/retrieval.py` - 检索模块
- [x] `src/llm_wiki/embeddings.py` - embedding 提供者抽象层
- [x] `wiki/.cache/embeddings.json` - 本地缓存
- [x] CLI 命令：`wiki index` - 建立/更新索引
- [x] 配置项：`config.yaml` 中启用/禁用 embedding

### 编辑器集成

- [ ] **Obsidian 插件**：
  - [ ] 显示页面状态（草稿/活跃/陈旧）
  - [ ] 一键触发 Ingest
  - [ ] 可视化 Lint 报告
- [ ] **VS Code 扩展**：
  - [ ] Wiki 预览
  - [ ] 链接补全

---

## 长期计划（6 个月+）

### 高级功能

- [ ] **MCP 服务器封装**：让其他 Agent（OpenClaw、OpenCode）也能使用
  ```
  本 wiki 作为 MCP 资源暴露：
  - resource://wiki/pages/{name}
  - tool://wiki/search
  - tool://wiki/ingest
  ```

- [ ] **多 Agent 协作**：
  - 一个 Agent 负责 Ingest
  - 另一个 Agent 负责审核和链接
  - 用户指定不同角色

- [ ] **版本对比**：
  - `wiki diff PageName --since 7d`
  - 查看概念随时间的演进

- [ ] **导出功能**：
  - 导出为静态站点（MkDocs/Hugo）
  - 导出为 PDF 电子书

### 规模化支持

- [ ] **分卷 wiki**：当单个仓库过大时，拆分为多个子 wiki
- [ ] **分层索引**：
  ```
  index.md                # Top-level index
  +-- ai/index.md         # AI sub-wiki index
  +-- sys/index.md        # System sub-wiki index
  ```
- [ ] **增量 Embedding 更新**：只更新修改页面的向量

---

## 技术债务

- [ ] 完善 `core.py` 的错误处理
- [ ] 添加单元测试（pytest）
- [ ] 类型检查（mypy）
- [ ] CI/CD 流程（GitHub Actions）

---

## 贡献指南

想参与开发？以下任务适合新贡献者：

1. **文档**：完善示例 wiki，修复 typo
2. **模板**：为你的领域创建 page_template
3. **Lint 规则**：添加新的健康检查项
4. **测试**：为 core.py 添加测试用例

见 [CONTRIBUTING.md](CONTRIBUTING.md)（待创建）

---

## 决策记录

### 2026-04-10：不用 Embedding

**决定**：v1.x 版本保持无 Embedding 设计

**理由**：
- 项目早期，简单比功能完整更重要
- 个人知识库通常 < 500 页，符号导航足够
- 维护好 index.md 本身就是知识整理的过程

**条件**：当页面 > 500 或用户明确要求时，启动 Embedding 支持

### 2026-04-14：Embedding 作为可选升级实现

**决定**：在 CLI 中增加可选的 embedding 混合检索支持，默认关闭

**实现**：

- Provider 抽象层支持 Ollama（本地）、OpenAI（远程 API）、MCP（通过 MCP 服务器调用）
- `wiki index` 命令建立增量索引，`wiki query --semantic` 使用混合检索
- 配置项 `embedding.enabled` 默认为 `false`，不影响现有纯符号导航用户

---

*最后更新：2026-04-14*
