# Subagent 注册表

## 当前开关
- configured gate: OFF
- effective gate this run: OFF
- 是否继续使用 subagents: 否
- 当前判断原因: F2.1 stayed in OFF mode because this round was a tightly coupled serial implementation.
- 最近事件: frontier_reselection_complete

## 当前集合
- 当前 active 实例: none
- 当前 blocked 实例: none
- 已退役: 019d42ac-a772-7941-ad79-df01220881c0, 019d42d7-e5fb-7793-8b11-ed23d0fb8448, 019d42ac-ace3-7ab2-addc-cb0136305ae4
- 已合并: none
- 已归档: none
- 已取消: none
- 已重构: none
- 临时实例: 019d42ac-a772-7941-ad79-df01220881c0, 019d42d7-e5fb-7793-8b11-ed23d0fb8448, 019d42ac-ace3-7ab2-addc-cb0136305ae4
- 长生命周期模板: none
- 当前 active 研究型: none
- 当前 active 基础设施型: none

## 本轮判断
- 建议数量: 0
- 建议角色: none
- 不拆分原因: The frontier reselection round is complete；no scout should remain active.
- 计划理由: Three temporary scouts were enough to rank R1.2, F2.1, and Hybrid F1.5；keep the gate OFF until implementation starts.

## 角色模板
- data_steward: 负责数据提供商、拉取、清洗与覆盖诊断，但不改动策略逻辑。
- strategy_auditor: 检查策略入口、默认配置和文档是否与现状研究发生漂移。
- validation_guard: 负责泄漏、稳健性、baseline 和 promotion gate 的验证工作。
- memory_curator: 保持 tracked memory、handoff 和 migration prompt 简洁、准确。
- tooling_scout: 在增加任何东西前，先查缺失工具、policy 文件和可复现边界。
- integration_merger: 合并可兼容的工作流、减少重复，并关停已完成的临时 subagent。

## 实例记录
### 019d42ac-a772-7941-ad79-df01220881c0 | scout | 已退休
- 类型: 基础设施型
- 摘要: Zeno frontier scout for F2.1
- 临时实例: 是
- 服务 blocker / 前提: post_r1_1_frontier_reselection
- 基础设施任务: structured latent deep factor and Deep SSM feasibility
- 交付结论: Returned defer for F2.1 as the next immediate build；keep it as runner-up behind a bounded R1.2 test.
- 这不是直接研究策略: Kept F2.1 as the runner-up challenger, not the next immediate build.
- 可写路径: none
- 预期产物: frontier_scout_report
- 产物目录: n/a
- 关闭或最近状态说明: Returned defer for F2.1 as the next immediate build；keep it as runner-up behind a bounded R1.2 test.
- 生命周期: parents=none; children=none; merged_into=n/a
### 019d42d7-e5fb-7793-8b11-ed23d0fb8448 | scout | 已退休
- 类型: 基础设施型
- 摘要: Popper frontier scout for R1.2
- 临时实例: 是
- 服务 blocker / 前提: post_r1_1_frontier_reselection
- 基础设施任务: gentler exposure-only regime overlay after R1.1
- 交付结论: Returned conditional go for R1.2 and ranked it ahead of F2.1 for the next near-term experiment.
- 这不是直接研究策略: Selected R1.2 as the next bounded challenger because the current blocker is drawdown control, not alpha shortage.
- 可写路径: none
- 预期产物: frontier_scout_report
- 产物目录: n/a
- 关闭或最近状态说明: Returned conditional go for R1.2 and ranked it ahead of F2.1 for the next near-term experiment.
- 生命周期: parents=none; children=none; merged_into=n/a
### 019d42ac-ace3-7ab2-addc-cb0136305ae4 | scout | 已退休
- 类型: 基础设施型
- 摘要: Fermat frontier scout for Hybrid F1.5
- 临时实例: 是
- 服务 blocker / 前提: post_r1_1_frontier_reselection
- 基础设施任务: frozen foundation-model sidecar feasibility next to F1
- 交付结论: Returned defer for Hybrid F1.5 because the current repo would need a heavier dependency/runtime stack.
- 这不是直接研究策略: Kept Hybrid F1.5 deferred until a frozen sidecar contract and offline reproducibility are proven.
- 可写路径: none
- 预期产物: frontier_scout_report
- 产物目录: n/a
- 关闭或最近状态说明: Returned defer for Hybrid F1.5 because the current repo would need a heavier dependency/runtime stack.
- 生命周期: parents=none; children=none; merged_into=n/a
