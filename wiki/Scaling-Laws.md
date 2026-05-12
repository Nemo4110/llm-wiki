---
created: "2026-05-13"
updated: "2026-05-13"
sources:
  - "sources/2601.20083.pdf"
source_types:
  - "academic_paper"
tags:
  - "AI/ML"
  - "Scaling Laws"
status: "active"
---

# Scaling Laws

Scaling laws 是描述模型性能如何随模型规模、数据规模、计算量或上下文长度变化而呈现可预测幂律/对数线性关系的经验规律。——[[Foundation Model]]

## 知识卡片

### 核心问题

当模型、数据和计算持续扩大时，性能提升是否可预测，以及哪些扩展维度是真正的瓶颈。

### 核心洞察

在 LLM 中，scaling laws 让研究者可以用小规模实验外推大模型表现；[[LLaTTE]] 的贡献是证明类似规律也可能出现在大规模广告推荐序列建模中，但推荐系统的 scaling 受语义特征、模型宽度、序列长度和生产时延共同制约。

### 机制/模型

推荐系统中的 scaling law 可粗略理解为：推荐效果 = f(序列长度, 模型深度, 模型宽度, 语义特征质量, 可用计算)。其中语义特征不是简单加分项，而是改变 scaling curve 斜率的条件变量。

### 适用边界

Scaling laws 是经验规律，不是理论保证。它们需要在具体数据分布、模型架构和业务目标下实验确认；跨领域迁移时尤其要检查指标、数据质量和 serving 约束是否一致。

### 与已有知识的关系

[[LLaTTE]] 将 scaling laws 从语言模型扩展到工业推荐系统；[[Foundation Model]] 页面提供了大模型扩展思想的背景。

## 来源笔记

### 来源：LLaTTE: Scaling Laws for Multi-Stage Sequence Modeling in Large-Scale Ads Recommendation

### 来源摘要

| 维度 | 内容 |
|---|---|
| **研究背景/目标** | 检验推荐系统序列建模是否存在类似 LLM 的可预测 scaling behavior。 |
| **方法** | 系统考察 depth、width、sequence length、semantic feature enrichment 和 cross-stage transfer dynamics。 |
| **结果** | 论文报告性能呈现可预测 log-linear scaling，语义内容 embedding 是更陡 scaling curve 的前提，模型 width 是 depth scaling 生效前的容量瓶颈。 |
| **结论** | 推荐系统可以从 scaling law 中获益，但扩容必须与语义特征和生产架构约束一起设计。 |

## 相关页面

- [[LLaTTE]] — 推荐系统中 scaling laws 的工业案例
- [[Foundation Model]] — scaling laws 在大模型中的背景
- [[Generative Recommendation]] — 推荐系统大模型化的另一条路线

## 来源

- [LLaTTE: Scaling Laws for Multi-Stage Sequence Modeling in Large-Scale Ads Recommendation](../sources/2601.20083.pdf)

## 变更日志

- 2026-05-13: 初始创建，基于 LLaTTE 论文提取推荐系统 scaling laws 概念
