# LLM-Wiki 路线图

> 项目演进计划和待办事项

## 当前状态：v1.4.0

**核心功能**：
- [x] 基于协议的 wiki 工作流
- [x] Ingest / Query / Lint 三大命令
- [x] 纯 Markdown，零外部强制依赖
- [x] Obsidian 兼容
- [x] Embedding 混合检索（Ollama / OpenAI / MCP）

**Agent 集成**：

- [x] **Agent Bridge 统一入口** — `scripts/agent-bridge.py` 零配置执行
- [x] **动态知识链接** — `link` / `relink` 自动发现页面关系
- [x] **双向内容合并** — 安全回写现有页面，自动备份
- [x] **执行可追溯性** — 文件级日志 `agent_logger.py`
- [x] **自动模式选择** — 根据 embedding 可用性自动切换 light/deep 模式

**CLI 工具**：

- [x] `wiki ingest` — 资料摄取
- [x] `wiki index` — Embedding 索引管理
- [x] `wiki link` — 单页面关系发现
- [x] `wiki relink` — 批量全局重新链接（支持 `--since` 增量）
- [x] `wiki lint` — 健康检查
- [x] `wiki query --semantic` — 语义检索

**数据处理**：

- [x] PyMuPDF PDF 解析
- [x] 本地 Embedding 缓存（`wiki/.cache/embeddings.json`）
- [x] 增量索引更新（修改页面定向重算）

**质量保障**：

- [x] 全面的 pytest 测试覆盖（`tests/`）
- [x] 类型注解（全代码库）

---

## 短期计划（1-2 个月）

### 核心体验优化

- [ ] **Lint 自动修复**：`--fix` 参数自动处理孤儿页面、死链
- [ ] **查询结果存档**：一键将回答保存为 wiki 页面
- [ ] **搜索历史**：记录常见查询，自动提示
- [ ] **增量 Ingest 优化**：对比文件 hash，仅处理真正变更的资料

### 模板和示例

- [ ] 领域模板包：
  - [ ] 学术研究模板
  - [ ] 技术研究模板
  - [ ] 读书笔记模板
- [ ] 5 个完整示例 wiki

---

## 中期计划（3-6 个月）

### 智能增强

- [ ] **关系图可视化**：基于链接数据生成概念关系图（Mermaid / Cytoscape）
- [ ] **知识冲突检测**：自动发现不同来源的矛盾陈述并标记
- [ ] **智能摘要**：长页面自动生成 TOC 摘要

---

## 长期计划（6 个月+）

### 生态集成

- [ ] **多 Agent 协作**：
  - 一个 Agent 负责 Ingest
  - 另一个 Agent 负责审核和链接
  - 用户指定不同角色

### 高级功能

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

---

## 技术债务

- [ ] 完善 `core.py` 错误处理（边界情况覆盖）
- [ ] 类型检查（mypy）纳入 CI
- [ ] CI/CD 流程（GitHub Actions）
- [ ] 性能基准测试（大规模 wiki 检索性能）
- [ ] 文档国际化同步机制（README 多语言自动检查）

---

## 贡献指南

想参与开发？以下任务适合新贡献者：

1. **文档**：完善示例 wiki，修复 typo
2. **模板**：为你的领域创建 page_template
3. **Lint 规则**：添加新的健康检查项
4. **测试**：提高边缘场景覆盖率

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

### 2026-04-21：动态链接与 Agent Bridge

**决定**：引入 `linker.py` + `merge.py` + `agent-bridge.py` 三层架构

**实现**：

- `linker.py`：基于标题/内容相似度发现页面关系（本地轻量或 Embedding 语义）
- `merge.py`：安全地将新内容合并到现有页面，支持多种策略（link_only / append_related / append_section）
- `agent-bridge.py`：Agent 唯一入口，自动检测环境、选择模式、输出结构化 Markdown
- 所有回写操作自动备份到 `wiki/.backups/`

### 2026-04-30：Agent Bridge 自动模式选择

**决定**：`agent-bridge.py link` 根据 embedding 可用性自动选择 light / deep 模式

**实现**：

- 检测 config.yaml 中 embedding 配置和本地依赖（numpy / httpx）
- 有 embedding → deep 模式（语义相似度计算）
- 无 embedding → light 模式（标题/标签/关键词匹配）
- 无需用户手动指定，零配置体验

---

*最后更新：2026-05-07*
