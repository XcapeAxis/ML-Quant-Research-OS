# 失败复盘

## 2026-03-27 Canonical Coverage Gap
- 失败路径: universe reset 后没有补 missing-only bars，导致旧 DB 残留和新 canonical universe 混在一起。
- 根因: `bars_registry.json` 仍停在旧池子规模，coverage gap 大量落在 `raw_never_attempted`。
- 修复: 改为 missing-only incremental backfill，并把截止日后上市样本单独标记为结构性无 bars。

## promotion-gate | promote_candidate
- 摘要: 当前候选仍被晋级门阻塞。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 拆解回撤究竟来自时间窗口集中、个股集中，还是持有尾部过长。
- 当前状态: 未修复

## 2026-03-30T02:18:32 | as_share_research_v1-20260330T021832
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复

## 2026-03-30T02:36:08+00:00 | as_share_research_v1__baseline_limit_up__20260330T023527Z
- 摘要: Bounded verifier blocked: missing_research_inputs: Rank dataframe is empty. Check coverage / min_bars / limit_days_window.
- 根因: missing_research_inputs: Rank dataframe is empty. Check coverage / min_bars / limit_days_window.
- 纠偏动作: Clarify the data boundary and the research range before comparing strategy outcomes.
- 当前状态: 未修复

## 2026-03-30T03:01:37 | as_share_research_v1-20260330T030137
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复

## 2026-03-30T07:04:19 | as_share_research_v1-20260330T070419
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复

## 2026-03-30T08:15:20 | as_share_research_v1-20260330T081520
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复

## 2026-03-30T08:17:51 | as_share_research_v1-20260330T081751
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复

## 2026-03-30T08:52:59 | as_share_research_v1-20260330T085259
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复

## 2026-03-30T09:55:03 | as_share_research_v1-20260330T095503
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复

## 2026-03-30T09:56:26 | as_share_research_v1-20260330T095626
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复

## 2026-03-30T12:01:36 | as_share_research_v1-20260330T120136
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复

## 2026-03-30T12:07:08 | as_share_research_v1-20260330T120708
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复

## 2026-03-31T06:37:19 | as_share_research_v1-20260331T063719
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复

## 2026-03-31T06:41:24+00:00 | as_share_research_v1__factor_elasticnet_core_r1_verify__20260331T064053Z
- 摘要: R1.1 bounded verifier did not improve drawdown enough.
- 根因: r1_annualized_return_delta -21.68% is below the allowed -3.00% floor.；r1_calmar_ratio_delta -0.1066 is not positive.
- 纠偏动作: Retain F1 mainline and re-run frontier reselection before choosing the next challenger.
- 当前状态: 未修复

## 2026-03-31T06:42:33 | as_share_research_v1-20260331T064233
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复

## 2026-03-31T06:47:01 | as_share_research_v1-20260331T064701
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复

## 2026-03-31T06:49:41+00:00 | as_share_research_v1__factor_elasticnet_core_r1_verify__20260331T064912Z
- 摘要: R1.1 bounded verifier did not improve drawdown enough.
- 根因: r1_annualized_return_delta -21.68% is below the allowed -3.00% floor.；r1_calmar_ratio_delta -0.1066 is not positive.
- 纠偏动作: Retain F1 mainline and re-run frontier reselection before choosing the next challenger.
- 当前状态: 未修复

## 2026-03-31T08:19:59 | as_share_research_v1-20260331T081959
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复

## 2026-03-31T08:21:38+00:00 | as_share_research_v1__factor_elasticnet_core__r1_predictive_error_overlay_v2__20260331T082058Z
- 摘要: R1.2 bounded verifier did not preserve enough economics to clear the gate.
- 根因: r1_annualized_return_delta -13.65% is below the allowed -3.00% floor.
- 纠偏动作: Retain F1 as the mainline and promote F2.1 to the next implementation slot.
- 当前状态: 未修复

## 2026-03-31T08:23:30+00:00 | as_share_research_v1__factor_elasticnet_core__r1_predictive_error_overlay_v2__20260331T082249Z
- 摘要: R1.2 bounded verifier did not preserve enough economics to clear the gate.
- 根因: r1_annualized_return_delta -13.65% is below the allowed -3.00% floor.
- 纠偏动作: Retain F1 as the mainline and promote F2.1 to the next implementation slot.
- 当前状态: 未修复

## 2026-03-31T08:29:35+00:00 | as_share_research_v1__factor_elasticnet_core__r1_predictive_error_overlay_v2__20260331T082915Z
- 摘要: R1.2 bounded verifier did not preserve enough economics to clear the gate.
- 根因: r1_annualized_return_delta -13.65% is below the allowed -3.00% floor.
- 纠偏动作: Retain F1 as the mainline and promote F2.1 to the next implementation slot.
- 当前状态: 未修复

## 2026-03-31T08:35:22+00:00 | as_share_research_v1__factor_elasticnet_core__r1_predictive_error_overlay_v2__20260331T083502Z
- 摘要: R1.2 bounded verifier did not preserve enough economics to clear the gate.
- 根因: r1_annualized_return_delta -13.65% is below the allowed -3.00% floor.
- 纠偏动作: Retain F1 as the mainline and promote F2.1 to the next implementation slot.
- 当前状态: 未修复

## 2026-03-31T08:37:21+00:00 | as_share_research_v1__factor_elasticnet_core__r1_predictive_error_overlay_v2__20260331T083703Z
- 摘要: R1.2 bounded verifier did not preserve enough economics to clear the gate.
- 根因: r1_annualized_return_delta -13.65% is below the allowed -3.00% floor.
- 纠偏动作: Retain F1 as the mainline and promote F2.1 to the next implementation slot.
- 当前状态: 未修复

## 2026-03-31T09:12:44 | as_share_research_v1-20260331T091244
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复

## 2026-03-31T10:01:53 | as_share_research_v1-20260331T100153
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复

## 2026-03-31T12:20:56 | as_share_research_v1-20260331T122056
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复

## 2026-03-31T12:41:24 | as_share_research_v1-20260331T124124
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复

## 2026-03-31T15:41:29 | as_share_research_v1-20260331T154129
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复

## 2026-03-31T15:43:12 | as_share_research_v1-20260331T154312
- 摘要: 晋级门阻塞： 最大回撤 48.67% 高于 30.00%。
- 根因: 最大回撤 48.67% 高于 30.00%。
- 纠偏动作: 先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。
- 当前状态: 未修复
