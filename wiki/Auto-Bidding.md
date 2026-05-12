---
created: "2026-04-16"
updated: "2026-04-30"
sources:
  - "sources/2510.23410.pdf"
tags:
  - "AI/ML"
  - "Computational Advertising"
status: "active"
---

# Auto-Bidding

自动出价（Auto-Bidding）是在线广告平台为广告主自动调整出价以优化广告效果（如 ROI、GMV、曝光量）的机制。——[[Real-Time Bidding]]

## Key Insights

- 传统 auto-bidding 模型通常针对特定场景（如某一类广告主、某一类商品）设计，导致跨场景泛化能力差
- Bid2X 提出将 auto-bidding 建模为统一的场景无关函数：给定出价，预测达成效果（预算消耗、GMV、曝光等）
- 该统一视角使 foundation model 范式可以应用于竞价环境，一个模型服务多种 bidding 场景

## Detailed Explanation

在在线广告生态中，auto-bidding 是连接广告主与广告平台的核心机制。广告主设定优化目标（如最大化 GMV 或 ROI），平台自动为每次竞价机会计算最优出价。传统方法包括规则-based 策略和强化学习模型，但都需要为每个场景单独训练。

Bid2X 的核心洞察是：无论场景如何变化，bidding 的底层逻辑都是"给定一组出价，预测对应的效果指标"。基于这一统一函数视角，Bid2X 将 heterogeneous bidding 数据编码为统一序列表示，学习场景无关的 bidding 环境动力学。该方法已在淘宝广告平台部署，线上 A/B 测试显示 GMV 提升 4.65%、ROI 提升 2.44%。

## Related Pages

- [[Bid2X]] — 基于 foundation model 的竞价环境统一建模
- [[Real-Time Bidding]] — 实时竞价的技术背景
- [[Foundation Model]] — 基础模型在竞价领域的应用
- [[Zero-Inflated Distribution]] — 出价数据中的零膨胀现象
- [[Generative Recommendation]] — 生成式推荐正在替代传统级联广告系统
- [[LLaTTE]] — 保留多阶段广告排序结构，但用长上下文 Transformer 用户模型增强 ranking 表征

## Sources

- [Bid2X: Revealing Dynamics of Bidding Environment in Online Advertising from A Foundation Model Lens](../sources/2510.23410.pdf)

## Changelog

- 2026-05-13: 添加 [[LLaTTE]] 作为广告推荐多阶段序列模型的相关路线
- 2026-04-30: 从 Bid2X 论文提取内容，补充 Key Insights 和 Detailed Explanation
