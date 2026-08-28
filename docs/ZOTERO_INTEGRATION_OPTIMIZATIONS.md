# Zotero 集成与附件管理优化方案

> 基于 Zotero 原生扩展 **ZotMoov** 的工程实践，为 `llm-wiki` 的文献层（Literature Layer）交互体系提供架构升级与健壮性优化指南。

---

## 1. 方案背景与定位

在 `llm-wiki` 架构中：
- **Zotero** 是文献底座（Literature Layer），负责文献元数据、原始附件、PDF 批注、分类目录（Collections）与引用键（Citation Keys）；
- **llm-wiki** 是蒸馏知识库（Distilled Markdown Knowledge Layer），负责概念提炼、跨源综合、双向链接与索引构建。

原生 Zotero 插件 **ZotMoov** 在长期的 Zotero 7/8 环境运行中，积累了处理底层文件系统兼容性、附件多模态、跨端同步竞态及引用链接自愈等方面的成熟设计模式。本文档梳理并提取这些优秀设计，作为 `llm-wiki` 后续在 Zotero 附件抽取、本地 API 写回与元数据维护等模块的优化依据。

---

## 2. 核心优化方案

### 方案一：跨平台文件名清洗与超长路径安全截断 (Sanitization & Path Guard)

#### 现有痛点
- 学术论文标题常包含特殊字符（如冒号 `:`、斜杠 `/`、反斜杠 `\`、问号 `?`、重音/变音符等），且长度常超过 150~200 字符。
- 在 Windows 环境下存在 **260 字符最大路径限制**（`MAX_PATH`），Linux/macOS 文件名存在 **255 字节限制**。
- `llm-wiki` 在生成 `wiki/<stem>.md` 页面名或 `sources/zotero/` 别名时，极易因超长路径或非法字符在跨平台同步时遭遇 IO 异常。

#### ZotMoov 的设计借鉴
- **智能标点与分词截断**（`src/00-zotmoov-wildcard.js`）：
  - 遇到冒号、问号等首个标点时优先截断为副标题前的内容；
  - 达到最大长度时，向前回溯至最近的单词边界（空格），避免截断单个单词。
- **字节级安全截断与后缀保护**（`lib/01-zotlib.js`）：
  - 精确计算 UTF-8 字节长度，严格预留文件扩展名（`.pdf` / `.md`）及唯一性冲突序号（如 ` 1.pdf`）的缓冲空间（预留 3~5 字节）。
- **音标/变音符号清理**：通过 `removeDiacritics` 去除变音符，确保 ASCII 兼容性。

#### `llm-wiki` 落地设计
在 `src/llm_wiki/` 中增加文件路径规范化工具（如 `path_sanitizer.py`）：
```python
def sanitize_title_stem(title: str, max_bytes: int = 120) -> str:
    """清理非法字符、去除音标、并在词边界安全截断以适配跨平台文件名"""
    ...
```

---

### 方案二：附件双模态解析与 Symlink 降级容错机制 (Attachment Dual-Mode & Fallback)

#### 现有痛点
- `scripts/zotero_sources.py` 强依赖于操作系统级符号链接（Symlink）创建 `sources/zotero/` 别名。
- **Windows 权限限制**：普通权限的 Windows 用户（未开开发者模式）无法创建 Symlink，导致脚本直接报错中断。
- **外部链接文件（Linked File）**：当用户使用了 ZotMoov 或 ZotFile 将附件存放在外部网盘（非 Zotero 内部 `storage/` 目录）时，单纯依赖默认 storage 路径无法正确解析文件。

#### ZotMoov 的设计借鉴
- **显式区分 Stored vs. Linked 模态**（`src/02-zotmoov.js`）：
  - 通过 `attachmentLinkMode` 区分存储附件与链接附件，使用 Zotero 官方 API `item.getFilePath()` 解析真实的绝对路径，不假设附件必然存在于 `storage/`。
- **降级容错机制**：如果无法建立软映射，提供只读复制或纯元数据映射。

#### `llm-wiki` 落地设计
修改 `scripts/zotero_sources.py`：
1. **真实物理路径检测**：支持通过 MCP 或 local API 提取 `item.getFilePath()`，无论附件是 Stored 还是 Linked 均能定位真实物理文件。
2. **Symlink 异常降级策略**：
   - 尝试创建 Symlink；
   - 若捕获 `OSError`（Windows 权限不足）：
     - 选项 A：降级为 Hardlink（硬链接，同一分区下无需管理员权限）；
     - 选项 B：降级为 Read-only Copy（只读副本）；
     - 选项 C：仅在 `metadata.yaml` 记录绝对路径映射，Agent 读取时直接路由到源路径，不强求本地实体别名文件。

---

### 方案三：Zotero 条目死链自愈与关联重映射 (Link Healing & Reconciliation)

#### 现有痛点
- `llm-wiki` 在 Wiki 页面 Frontmatter 中记录了 `zotero_item_key`。
- 科研工作流中，用户常在 Zotero 中执行“条目合并（Merge Items）”、“重新从 DOI 导入条目并删除旧项”或“转换附件”。此时 Wiki 页面中记录的旧 `item_key` 将悬空失效，导致后续 `zotero-refresh` 或写回操作失败。

#### ZotMoov 的设计借鉴
- **笔记与关联自愈算法**（`src/02-zotmoov-menu-helper.js`）：
  - 遍历 Zotero 笔记中的引用 URI，检测引用的旧条目是否已在数据库中删除；
  - 若已删除，自动基于关联信息或父条目检索有效的新条目 Key，并调用 `replaceItemKey` 全局修复。

#### `llm-wiki` 落地设计
在 `src/llm_wiki/zotero_ingest_verify.py` 和 `zotero_refresh.py` 中引入**条目自愈管道**：
1. **失效 Key 探测**：当 `zotero_get_item_metadata` 返回 404/not found 时，标记为待修复悬空条目。
2. **多维二次寻址**：
   - 优先通过 Wiki Frontmatter 中的 `doi` 查询 Zotero 库匹配有效条目；
   - 次优通过 `citation_key` 或标准化标题（Title matching）匹配有效条目；
3. **自动迁移修复**：在用户确认或 `--apply-safe` 模式下，自动更新受影响 Wiki 文件的 `zotero_item_key`，并在 `log.md` 记录自愈日志。

---

### 方案四：双向关系原子性与同步状态隔离防护 (Transactional Relations & Sync Guard)

#### 现有痛点
- `llm-wiki` 在 `src/llm_wiki/zotero_local.py` 中支持互关写入（`dc:relation`）。
- 若在执行双向关联时，Source 条目写入成功而 Target 条目写入失败（或遇网络/版本冲突），会在 Zotero 中留下单向不对称的残缺关联。
- 大规模写回时若恰逢 Zotero 后台云端同步，容易产生版本冲突（HTTP 412）。

#### ZotMoov 的设计借鉴
- **同步挂起协调**（`src/01-zotmoov-notify-callback.js`）：
  - 在大批量写入期间，通知同步器推迟后台同步（`Zotero.Sync.Runner.delayIndefinite()`），全部原子写入完成后再恢复同步。
- **两阶段事务与回滚**：
  - 核心写操作均置于事务块内，任何一步异常立即清理并回滚。

#### `llm-wiki` 落地设计
1. **两阶段关系写入与补偿机制**：
   - 在 `zotero_local.py` 中写入 `RelationWriteResult` 时，如果第二阶段失败，自动向第一阶段的 Source 条目触发补偿回滚，移除刚刚新增的关联 URI，确保双向关联的原子一致性。
2. **同步状态检测门禁强化**：
   - 强化 `docs/ZOTERO_MCP_INTEGRATION.md` 中定义的 `metadata_sync_state` 检测，在检测到 Zotero 处于同步活跃期时自动等待或增加退避重试延迟。

---

### 方案五：基于通配符与层级目录的元数据模板引擎 (Wildcard Template Engine)

#### 现有痛点
- 目前从 Zotero 导入条目到 `llm-wiki` 时，文件命名与目录结构规则较为单一，缺乏对 Zotero 分类树（Collection Hierarchy）和自定义命名格式的灵活支持。

#### ZotMoov 的设计借鉴
- **多层级分类路径解析**（`src/00-zotmoov-wildcard.js`）：
  - 递归遍历父 Collection，生成标准层级路径（如 `Machine Learning/LLM/Reasoning`）。
- **统一通配符体系**：
  - `%a` (主作者)、`%y` (年份)、`%t` (截断标题)、`%c` (分类路径)、`%b` (CiteKey)、`%T` (条目类型)。

#### `llm-wiki` 落地设计
在 `config.yaml` 中允许用户自定义 Zotero 导入及 Wiki 页面命名的模板规则：
```yaml
zotero_import:
  page_template_pattern: "%c/%y-%a-%t"
  alias_pattern: "%b"
```

---

## 3. 实施优先级路线图

| 阶段 | 优先级 | 优化内容 | 涉及模块 |
| :--- | :---: | :--- | :--- |
| **Phase 1** | **P0** | **路径清洗截断工具**：引入字节级文件名截断与非法字符清洗 | `src/llm_wiki/sanitizer.py`, `scripts/zotero_sources.py` |
| **Phase 1** | **P0** | **Symlink 降级与 Linked File 支持**：解决 Windows 权限与外部附件路径解析 | `scripts/zotero_sources.py`, `docs/FILE_HANDLING.md` |
| **Phase 2** | **P1** | **条目死链自愈机制**：支持条目合并/变更时的自动 DOI/CiteKey 重映射 | `src/llm_wiki/zotero_refresh.py`, `zotero_ingest_verify.py` |
| **Phase 2** | **P1** | **双向关系原子补偿**：确保 `dc:relation` 写入失败时的回滚一致性 | `src/llm_wiki/zotero_local.py` |
| **Phase 3** | **P2** | **可配置通配符模板引擎**：支持按 Collection 层级自定义生成路径与别名 | `src/llm_wiki/zotero_plan.py`, `config.yaml` |
