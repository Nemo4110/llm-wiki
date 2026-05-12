---
created: "2026-05-13"
updated: "2026-05-13"
sources:
  - "sources/2601.20083.pdf"
source_types:
  - "academic_paper"
tags:
  - "AI/ML"
  - "Advertising"
  - "Recommender Systems"
  - "Scaling Laws"
status: "active"
---

# LLaTTE

LLaTTE（LLM-Style Latent Transformers for Temporal Events）是 Meta 在生产广告推荐中部署的多阶段 Transformer 序列建模架构，用于把 [[Scaling Laws]] 引入大规模推荐系统。——[[Generative Recommendation]]

## 知识卡片

### 核心问题

大规模广告推荐天然是用户事件序列建模问题，但生产系统长期受限于毫秒级在线排序延迟、FM 类稀疏特征架构和非序列特征融合难题，无法像 LLM 那样简单通过更深模型、更长上下文和更多计算获得稳定收益。

### 核心洞察

LLaTTE 的关键结论是：推荐系统的序列建模也存在类似 LLM 的可预测扩展规律，但 scaling 不是“堆 Transformer 层数”本身带来的，而是由语义特征、足够模型宽度、长序列上下文和多阶段计算分摊共同解锁的。

### 机制/模型

LLaTTE = Target-Aware Adaptive Transformer × Multi-Stage Architecture × Semantic Feature Enrichment × Upstream User Model。

它把重型长上下文序列编码放到异步上游用户模型中，在高价值用户事件触发时生成并缓存压缩用户 embedding；在线 ranking 阶段只融合缓存 embedding 与短期新鲜序列信号，从而把大部分序列计算移出请求时延路径。

### 适用边界

该方法最适合高流量、强序列行为、具备丰富语义特征且能承受异步用户表征更新的工业推荐系统。对于低流量推荐、缺少内容理解 embedding 的系统，或强依赖实时上下文但难以缓存用户表征的场景，LLaTTE 的 scaling 收益可能无法直接复现。

### 与已有知识的关系

- 相比 [[Generative Recommendation]] 把推荐改写为 item/SID 生成，LLaTTE 保留多阶段 ranking 范式，但用 Transformer 长序列用户模型增强排序表征。
- 相比传统 [[CTR Prediction]] 中 DIN/DIEN 一类浅层兴趣序列模型，LLaTTE 关注深层、长上下文 Transformer 的可扩展规律。
- 相比 [[Foundation Model]] 在广告系统中的环境建模，LLaTTE 的核心对象是用户时序行为和广告推荐 ranking，而不是统一建模竞价环境。
- 它把 [[Scaling Laws]] 从语言模型迁移到工业推荐系统，但强调语义特征是弯折 scaling curve 的前提。

## 来源笔记

### 来源：LLaTTE: Scaling Laws for Multi-Stage Sequence Modeling in Large-Scale Ads Recommendation

### 来源摘要

| 维度 | 内容 |
|---|---|
| **研究背景/目标** | 研究生产广告推荐中的序列模型能否像 LLM 一样呈现可预测 scaling law，并在严格在线时延约束下实际部署。 |
| **方法** | 提出 LLaTTE：Target-Aware Adaptive Transformer 负责融合候选、非序列稀疏特征和用户事件序列；Multi-Stage Architecture 用异步 upstream user model 承担大规模长上下文计算，在线 ranking 阶段使用缓存 embedding。 |
| **结果** | 论文报告性能遵循可预测 log-linear scaling；序列长度是主要杠杆；语义内容 embedding 会改变 scaling 曲线；upstream 改进约 50% 可迁移到在线排序；部署后主收入模型 Normalized Entropy 提升 0.25%，Facebook Feed 和 Reels conversion uplift 达 4.3%。 |
| **结论** | 工业推荐系统可以利用类似 LLM 的扩展规律，但必须同时解决语义特征、模型宽度、长上下文和 serving latency 的系统约束。 |

### 论文四要素

| 要素 | 内容 |
|---|---|
| **根本问题** | 如何在生产广告推荐的严格在线时延约束下，让深层长上下文序列模型获得可预测 scaling 收益。 |
| **切入视角** | 把用户推荐行为视为可扩展的 temporal event sequence，并把 heavy sequence modeling 从在线请求路径拆到异步 upstream 用户模型。 |
| **关键方法** | Target-aware adaptive Transformer 解决候选/非序列特征融合；multi-stage architecture 通过缓存用户 embedding 分摊计算。 |
| **核心发现** | 推荐序列建模存在可预测 scaling law，但语义特征和足够宽度是深度、长度 scaling 生效的前提；upstream 序列模型收益能高比例传导到在线 ranking。 |

### 证据与局限

- **关键证据**：论文第一页明确作者来自 AI at Meta；摘要报告 LLaTTE 是 Meta 最大的 user model，并带来 Facebook Feed/Reels 4.3% conversion uplift；正文报告 upstream 模型消耗超过在线 counterpart 45× sequence FLOPs。
- **主要局限**：论文公开的是生产广告推荐场景，许多系统细节、数据分布和业务目标无法完全复现；指标收益未必能迁移到非广告或非 Meta 规模系统。
- **未来方向**：验证 scaling law 在自然内容推荐、搜索排序、电商推荐和生成式推荐中的迁移性；研究语义特征质量与模型规模之间的最优配比。

## 相关页面

- [[Generative Recommendation]] — 另一条用生成模型重构推荐流水线的路线
- [[CTR Prediction]] — LLaTTE 所增强的广告 ranking/CTR 预测技术背景
- [[Real-Time Bidding]] — 生产广告系统的在线时延与排序约束背景
- [[Foundation Model]] — 大模型/基础模型思想在广告系统中的应用背景
- [[Scaling Laws]] — LLaTTE 迁移到推荐系统的核心规律

## 来源

- [LLaTTE: Scaling Laws for Multi-Stage Sequence Modeling in Large-Scale Ads Recommendation](../sources/2601.20083.pdf)

## 变更日志

- 2026-05-13: 初始创建，基于 arXiv:2601.20083 提取 LLaTTE 的多阶段序列建模与推荐 scaling law 机制
