# Wiki Log

## [2026-05-13] ingest | LLaTTE: Scaling Laws for Multi-Stage Sequence Modeling in Large-Scale Ads Recommendation

- Source: [arXiv:2601.20083](sources/2601.20083.pdf)
- New: [[LLaTTE]], [[Scaling Laws]]
- Updated: [[Generative-Recommendation]] (added comparison with LLaTTE as multi-stage sequence modeling route)
- Key insight: Meta 的 LLaTTE 证明大规模广告推荐序列建模也可以呈现类似 LLM 的 scaling law，但语义特征、模型宽度、长上下文和异步 upstream user model 是在生产时延约束下释放扩展收益的关键。

## [2026-05-12] ingest | 广告生成式推荐三篇论文（GPR + GR4AD + UniVA）

- Source: [广告生成式推荐应该怎么做：融合三篇的系统设计观](https://zhuanlan.zhihu.com/p/2036546189705918125)
- New: [[GPR]], [[GR4AD]], [[UniVA]], [[Semantic-ID]], [[Generative Recommendation]]
- Updated: [[Generative-AI]], [[GRPO]], [[Auto-Bidding]], [[Real-Time-Bidding]] (added bidirectional links)
- Key insight: 广告生成式推荐通过 Semantic ID + 自回归生成替代传统召回-排序级联范式，三篇论文已在亿级用户规模全量部署（GPR: GMV +5%+, GR4AD: 广告收入 +4.2%, UniVA: GMV +1.5%）
- Core design principles: 商业价值从 tokenization 阶段渗透；异构输入需 Token-Aware 架构；RL 探索但 simulator 质量是核心风险

## [2026-04-16] ingest | Bid2X: Bidding Environment Foundation Model

- New: [[Bid2X]], [[Auto-Bidding]], [[Foundation Model]], [[Real-Time Bidding]], [[Zero-Inflated Distribution]]
- Key insight: Unified sequence embedding for heterogeneous bidding data

## [2026-04-16] ingest | RTBAgent: LLM-based Real-Time Bidding Agent

- New: [[RTBAgent]], [[LLM Agent]], [[CTR Prediction]]
- Key insight: Multi-memory retrieval mechanism for adaptive bidding

## [2026-04-16] ingest | LLP: LLM-based Product Pricing in E-commerce

- New: [[LLP]], [[C2C E-commerce]], [[Generative Product Pricing]], [[GRPO]], [[RAG]]
- Key insight: Two-stage SFT+GRPO optimization for C2C pricing

## [2026-04-16] ingest | Pricing and Competition for Generative AI

- New: [[Pricing and Competition for Generative AI]], [[Generative AI]], [[Game Theory]], [[Price-Performance Ratio]], [[User Satisfaction]]
- Key insight: Sequential pricing game model for competitive generative AI markets

## [2026-04-30] lint | Protocol compliance check

- Updated: 14 stub pages — added missing `sources` frontmatter and standard sections
- Fixed: requirements.txt — added fallback PDF dependencies (pdfplumber, pdfminer.six)

## [2026-04-30] ingest | Content extraction from 4 source PDFs

- Source: sources/2510.23410.pdf (Bid2X), sources/2502.00792v1.pdf (RTBAgent), sources/2510.09347.pdf (LLP), sources/2411.02661.pdf (Pricing and Competition for Generative AI)
- Fixed: [[Bid2X]], [[RTBAgent]], [[LLP]] — corrected `sources` frontmatter to point to actual PDF files
- Updated (filled Key Insights + Detailed Explanation):
  - Bid2X paper stubs: [[Auto-Bidding]], [[Foundation Model]], [[Real-Time Bidding]], [[Zero-Inflated Distribution]]
  - RTBAgent paper stubs: [[LLM Agent]], [[CTR Prediction]]
  - LLP paper stubs: [[C2C E-commerce]], [[Generative Product Pricing]], [[GRPO]], [[RAG]]
  - Pricing paper stubs: [[Generative AI]], [[Game Theory]], [[Price-Performance Ratio]], [[User Satisfaction]]
- Enriched main pages: [[Bid2X]], [[RTBAgent]], [[LLP]], [[Pricing and Competition for Generative AI]] — added Detailed Explanation sections
- Key insight: All 18 wiki pages now have substantial content sourced from original PDFs; no more empty stub pages
