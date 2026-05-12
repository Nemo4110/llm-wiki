---
created: "2026-04-16"
updated: "2026-04-30"
tags:
  - "AI/ML"
  - "Computational Advertising"
  - "Foundation Model"
  - "KDD 2025"
sources:
  - "sources/2510.23410.pdf"
status: "active"
---

# Bid2X

Bid2X 是阿里巴巴提出的**竞价环境基础模型**（bidding foundation model），用于统一建模在线广告中的自动出价环境。

## 核心要点

- **问题**：传统 auto-bidding 模型针对特定场景设计，难以跨场景泛化
- **方法**：将不同出价场景的数据编码为统一序列表示，通过 attention 机制建模变量间和时间上的动态依赖
- **创新点**：
  - 统一序列嵌入（uniform series embeddings）处理异构数据
  - 变量感知融合模块（variable-aware fusion）自适应预测出价结果
  - 零膨胀投影模块（zero-inflated projection）处理出价数据中的大量零值
- **效果**：在淘宝广告平台部署，线上 A/B 测试提升 GMV 4.65%、ROI 2.44%

## Detailed Explanation

Bid2X 的整体架构包含三个核心模块：

### 1. 统一序列嵌入（Uniform Series Embeddings）

Bidding 数据具有高度异构性：不同场景的广告主关注不同目标（预算消耗、GMV、曝光量等），数据字段和分布各不相同。Bid2X 将每个 bidding 记录编码为统一序列表示，通过 tailored embedding 方法处理数值型、类别型和时间型特征，使不同场景的数据可以在同一空间中表示。

### 2. 双注意力机制（Dual Attention）

Bidding 数据中存在两类复杂依赖：

- **变量间依赖**：不同特征（如预算、出价、CTR）之间存在复杂的交互关系
- **时间动态**：历史 bidding 序列的趋势和周期性影响当前预测

Bid2X 提出分别将变量嵌入和时间嵌入作为 attention token，通过两个独立的注意力层分别建模这两类依赖，再融合得到最终表示。

### 3. 零膨胀投影（Zero-Inflated Projection）

由于大部分出价不会获胜，目标变量（如转化量）呈现零膨胀分布。Bid2X 通过联合优化分类损失（判断是否非零）和回归损失（预测非零值的大小），使模型预测收敛到真实的零膨胀分布，而非简单预测均值。

## 相关概念

- [[Auto-Bidding]] — 自动出价服务
- [[Foundation Model]] — 基础模型范式
- [[Real-Time Bidding]] — 实时竞价
- [[Zero-Inflated Distribution]] — 零膨胀分布
- [[LLaTTE]] — 同属广告推荐大模型化路线，但聚焦用户长序列 ranking 表征而非竞价环境动力学

## 相关页面

- [[RTBAgent]] — 同为竞价领域的 LLM 代理系统
- [[LLP]] — 电商领域的 LLM 定价应用
- [[Pricing and Competition for Generative AI]] — 生成式 AI 的定价博弈分析

## 来源

- [Bid2X: Revealing Dynamics of Bidding Environment in Online Advertising from A Foundation Model Lens](../sources/2510.09347.pdf)

## 变更日志

- 2026-04-16: 初始创建
- 2026-05-13: 添加 [[LLaTTE]] 作为广告推荐大模型化的相关路线
- 2026-04-30: 补充变更日志 section
