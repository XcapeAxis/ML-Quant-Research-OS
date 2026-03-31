# 前沿算法侦察结论（2026-03-30）

## 侦察范围
- 时间范围：2023-2026
- 市场范围：以 A 股日/周频研究为落脚点，但允许借用全球高质量文献做方法判断
- 目标：找“因子优先 + 可控机器学习优先”的高潜力路线，而不是继续把单一规则策略当终局

## 总结论
- 最稳的首发方向不是黑箱深度网络，也不是继续深挖单一规则策略。
- 最合理的首发栈是：
  1. `正则化横截面因子模型`：`Regularized Fama-MacBeth / CS-C-ENet`
  2. `结构化 latent deep factor`：`条件自编码器 / 小瓶颈 + 线性或浅层定价头`
  3. `结构化市场信息分支`：`供应链/相似度网络事件传播 alpha`
  4. `控制层能力`：`graph regime + regime-aware 组合`
  5. `受控 challenger`：`异质性稀疏线性 / P-Trees / 单调约束 boosting / GAM`

## 优先级排序
### P1 首发 MVP
- `正则化横截面因子模型`
- 适合原因：
  - 与“因子优先 + 可解释/可控”最一致
  - 工程迁移成本最低
  - 可直接成为后续 deep factor 和结构化分支的 benchmark
  - 比继续做单一规则策略更像真正的研究平台起点

### P2 第二阶段
- `结构化 latent deep factor`
- 适合原因：
  - 比全量 Transformer 更稳
  - 可以保留小因子头和解释层
  - 更适合做周频和双周频的第二阶段 challenger

### P3 独特 alpha 分支
- `供应链/相似度网络事件传播 alpha`
- 适合原因：
  - 与普通多因子差异大
  - 审计性较强
  - 很适合做成平台中的独立 branch

### P4 平台级控制层
- `graph regime + regime-aware 组合`
- 适合原因：
  - 它更像平台能力，而不是单条 alpha
  - 可以服务多条分支

### P5 受控 challenger
- `异质性稀疏线性`
- `P-Trees / 面板树`
- `单调约束 boosting`
- `GAM / EBM`

## 暂不优先
- `全量 tabular/time-series transformer`
- `RL / LLM 直接选股`
- `Asset Embeddings`
- `TabPFN` 作为主线
- `纯文本财报/电话会直接预测`

## 平台含义
- 单一规则策略分支保留，但只保留为：
  - control branch
  - smoke test
  - baseline benchmark
- 平台主对象应升级为：
  - `FactorCandidate`
  - `FeatureView`
  - `LabelSpec`
  - `ModelCandidate`
  - `EvaluationRecord`
  - `BranchScoreCard`
  - `FailurePattern`

## 直接影响到的 slice
1. `P0`：修 truth layer
2. `F0`：补 factor/feature/label/model 对象层
3. `F1`：做 `Regularized Fama-MacBeth / CS-C-ENet` MVP
4. `F2`：做 `structured latent deep factor` challenger
5. `X1`：做 `供应链/相似度网络事件传播` 分支 PoC
6. `R1`：做 `graph regime + regime-aware 组合` 控制层

## 关键来源
- [AQR: Fact, Fiction, and Factor Investing (2022-12-22)](https://www.aqr.com/Insights/Research/Journal-Article/Fact-Fiction-and-Factor-Investing)
- [Han et al., Review of Finance (2024-08-20)](https://doi.org/10.1093/rof/rfae027)
- [Evgeniou et al., JFQA (2023-12)](https://doi.org/10.1017/S0022109022001028)
- [Cong et al., JFE (2025-05)](https://doi.org/10.1016/j.jfineco.2025.104024)
- [Lin et al., SSRN (2024-04-18)](https://ssrn.com/abstract=4799906)
- [Kruschel et al., arXiv (2024-09-22)](https://arxiv.org/abs/2409.14429)
- [Fan et al., SSRN (2023)](https://ssrn.com/abstract=4117882)
- [Chen et al., Management Science (2024)](https://doi.org/10.1287/mnsc.2023.4695)
- [Zhu et al., Finance Research Letters (2025)](https://doi.org/10.1016/j.frl.2025.108519)
- [CQVAE, JBES (2024)](https://doi.org/10.1080/07350015.2023.2223683)
- [RVRAE, arXiv (2024-03-04)](https://arxiv.org/abs/2403.02500)
- [Spillover Effects Within Supply Chains, SSRN/JIFMA (2023-07-17)](https://ssrn.com/abstract=4504016)
- [Stock Price Responses to Firm-Level News in Supply Chain Networks, SSRN (2024-10-04)](https://ssrn.com/abstract=4943313)
- [Representation Learning for Regime Detection in Block Hierarchical Financial Markets, arXiv (2024-10-14)](https://arxiv.org/abs/2410.22346)
- [Explainable Regime Aware Investing, arXiv (2026-02-21)](https://arxiv.org/abs/2603.04441)
- [AlphaLogics, arXiv (2026-03-10)](https://arxiv.org/abs/2603.20247)
- [R&D-Agent-Quant, arXiv (2025-05-21)](https://arxiv.org/abs/2505.15155)
- [Towards an AI co-scientist, arXiv (2025-02-26)](https://arxiv.org/abs/2502.18864)
- [AlphaForge, arXiv (2024-06-26)](https://arxiv.org/abs/2406.18394)
