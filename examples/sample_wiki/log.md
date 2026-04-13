# Wiki Log

## [2026-04-10] init | 项目初始化
- 创建 llm-wiki 结构
- 初始化 CLAUDE.md 协议 v1.0.0

## [2026-04-10] ingest | Attention Is All You Need
- 新增页面：
  - [[Transformer]] — 完整架构概述
  - [[Self-Attention]] — 核心机制
  - [[Multi-Head Attention]] — 多头实现细节
  - [[Positional Encoding]] — 位置编码
- 更新页面：
  - [[NLP 架构演进]] — 添加 Transformer 章节
- 关键洞察：
  - Transformer 用纯注意力替代了 RNN 的循环结构
  - 可并行化带来了训练效率的质的飞跃
  - 成为后续 GPT、BERT 等所有大模型的基础

## [2026-04-10] query | "Transformer vs RNN"
- 用户问题：Transformer 和 RNN 有什么区别？
- 已创建回答页面：[[Transformer vs RNN]]
- 主要区别：并行性、长距离依赖、计算复杂度
