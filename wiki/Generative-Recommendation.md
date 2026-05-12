---
created: "2026-05-12"
updated: "2026-05-12"
sources:
  - "sources/2511.10138.pdf"
  - "sources/2602.22732.pdf"
  - "sources/2605.05803.pdf"
  - "sources/2601.20083.pdf"
tags:
  - "AI/ML"
  - "Advertising"
  - "Generative Recommendation"
status: "active"
---

# Generative Recommendation

生成式推荐（Generative Recommendation，GR）是一种将推荐问题改写为"下一个 token 预测"的范式：给每个物品分配一串离散的 [[Semantic-ID]]，训练自回归语言模型给定用户历史逐层生成这串编码，一个模型端到端完成传统召回+排序的全部工作。——[[Generative AI]]

## Key Insights

- 传统推荐系统是"从候选集里打分选出最好的"，GR 是"直接生成用户最可能感兴趣的物品"
- GR 在内容推荐（短视频、文章）中已被证明可以跑赢传统流水线
- 广告场景的额外挑战：需要同时生成"用户喜欢的"和"商业价值高的"物品
- 三篇工业生成式推荐论文（[[GPR]]、[[GR4AD]]、[[UniVA]]）已在亿级用户规模全量部署
- [[LLaTTE]] 代表另一条大模型化路线：不直接生成 item，而是在传统多阶段广告排序中用长上下文 Transformer user model 引入 [[Scaling Laws]] 思路

## Detailed Explanation

### 范式迁移

传统广告推荐系统是一条流水线：召回（从千万级广告库筛出几百个候选）→ 粗排（初步打分）→ 精排（精细计算 eCPM）。这条流水线跑了十几年，但有两个根本性结构缺陷：

1. **信息瓶颈**：召回阶段丢掉的广告，后续所有模块都无法找回
2. **目标不对齐**：召回追覆盖率，精排追 eCPM，没有统一的端到端目标

GR 用单一生成模型替代整条流水线，将推荐改写为自回归序列生成任务。

### 广告 GR 的四大核心问题

1. **怎么给广告编码**（SID 设计）：见 [[Semantic-ID]]
2. **模型结构怎么设计**：异构输入需要 Token-Aware 参数，见 [[GPR]] 的 HHD 架构
3. **怎么训练**：三阶段训练（SFT → 价值微调 → RL），见 [[GPR]] 的 MTP/VAFT/HEPO
4. **线上怎么 serving**：Beam Search + 个性化 Trie + 价值融合，见 [[UniVA]]

### 设计原则提炼

- **商业价值必须从 tokenization 阶段就开始渗透**，而不是在末端打补丁
- **广告输入的异构性必须在架构上正视**，不能用均一参数混合处理
- **RL 探索是必要的，但 simulator 质量是核心风险**

### 与 LLaTTE 的关系

[[LLaTTE]] 并不把推荐直接改写为 item token 生成，而是保留生产广告系统的多阶段 ranking 结构，在用户序列建模层引入 LLM-style Transformer 和 scaling law 思想。它与 GPR/GR4AD/UniVA 的共同点是都把推荐系统推向大模型化；差异在于 LLaTTE 优先解决“长上下文用户表征如何在毫秒级 serving 约束下扩容”，而生成式推荐优先解决“如何端到端生成候选 item/SID”。

## Related Pages

- [[GPR]] — 腾讯微信视频号，双解码器 + MTP + VAFT + HEPO，GMV +5%+
- [[GR4AD]] — 快手，单解码器 + LazyAR + RSPO，广告收入 +4.2%
- [[UniVA]] — 腾讯，Commercial SID + Generation-as-Ranking，GMV +1.5%
- [[Semantic-ID]] — GR 的核心组件，离散语义编码
- [[LLaTTE]] — 推荐系统大模型化的多阶段序列建模路线
- [[Scaling Laws]] — LLaTTE 引入推荐系统的扩展规律
- [[Generative-AI]] — 生成式 AI 基础概念
- [[Auto-Bidding]] — 传统广告系统的出价模块
- [[Real-Time-Bidding]] — 广告实时竞价背景

## Sources

- [GPR](../sources/2511.10138.pdf)
- [GR4AD](../sources/2602.22732.pdf)
- [UniVA](../sources/2605.05803.pdf)
- [LLaTTE](../sources/2601.20083.pdf)

## Changelog

- 2026-05-13: 补充 [[LLaTTE]] 作为广告推荐大模型化的多阶段序列建模路线
- 2026-05-12: 初始创建，综合三篇论文和知乎综述文章
