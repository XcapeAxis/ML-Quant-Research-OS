# 失败复盘

当前 bootstrap 状态尚无失败复盘。后续仅追加高信号失败，记录根因、纠偏动作和当前状态。

## promotion-gate | promote_candidate
- 摘要: Candidate failed the current promotion gate.
- 根因: missing_research_inputs: No bars found for requested codes.
- 纠偏动作: 在下一次 promotion 前，先解决当前 gate 失败原因。

## 2026-03-24T16:22:54 | as_share_research_v1-20260324T162254
- 摘要: Dry-run blocked by missing research inputs: No bars found for requested codes.
- 根因: missing_research_inputs: No bars found for requested codes.
- 纠偏动作: Restore a usable frozen universe plus local bars before rerunning the dry-run cycle.

## promotion-gate | promote_candidate
- 摘要: Candidate failed the current promotion gate.
- 根因: 最大回撤 83.38% 高于 30.00%。
- 纠偏动作: 在下一次 promotion 前，先解决当前 gate 失败原因。
- 当前状态: 未修复

## 2026-03-25T08:18:01+00:00 | as_share_research_v1-20260325T081801+0000
- 摘要: 晋级门阻塞： 最大回撤 56.50% 高于 30.00%。
- 根因: 最大回撤 56.50% 高于 30.00%。
- 纠偏动作: 基于策略失败报告设计下一轮以风险为中心的实验。
- 当前状态: 未修复

## promotion-gate | promote_candidate
- 摘要: Candidate failed the current promotion gate.
- 根因: 最大回撤 56.50% 高于 30.00%。
- 纠偏动作: 基于 STRATEGY_FAILURE_REPORT 设计下一轮以风险为中心的实验。
- 当前状态: 未修复

## 2026-03-25T08:23:26+00:00 | as_share_research_v1-20260325T082326+0000
- 摘要: 晋级门阻塞： 最大回撤 56.50% 高于 30.00%。
- 根因: 最大回撤 56.50% 高于 30.00%。
- 纠偏动作: 基于策略失败报告设计下一轮以风险为中心的实验。
- 当前状态: 未修复

## promotion-gate | promote_candidate
- 摘要: Candidate failed the current promotion gate.
- 根因: 最大回撤 56.50% 高于 30.00%。
- 纠偏动作: 基于 STRATEGY_FAILURE_REPORT 设计下一轮以风险为中心的实验。
- 当前状态: 未修复

## 2026-03-25T14:35:07+00:00 | as_share_research_v1__legacy_single_branch__20260325T143507Z
- 摘要: 晋级门阻塞： 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 根因: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 纠偏动作: 结合策略失败报告和 branch ledger，选择下一轮 bounded branch experiment。
- 当前状态: 未修复

## 2026-03-25T15:02:31+00:00 | as_share_research_v1__legacy_single_branch__20260325T150231Z
- 摘要: 晋级门阻塞： 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 根因: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 纠偏动作: 结合策略失败报告和 branch ledger，选择下一轮 bounded branch experiment。
- 当前状态: 未修复

## 2026-03-25T15:09:15+00:00 | as_share_research_v1__legacy_single_branch__20260325T150915Z
- 摘要: 晋级门阻塞： 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 根因: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 纠偏动作: 结合策略失败报告和 branch ledger，选择下一轮 bounded branch experiment。
- 当前状态: 未修复

## 2026-03-25T15:15:28+00:00 | as_share_research_v1__legacy_single_branch__20260325T151529Z
- 摘要: 晋级门阻塞： 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 根因: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 纠偏动作: 结合策略失败报告和 branch ledger，选择下一轮 bounded branch experiment。
- 当前状态: 未修复

## 2026-03-25T15:22:12+00:00 | as_share_research_v1__legacy_single_branch__20260325T152213Z
- 摘要: 晋级门阻塞： 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 根因: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 纠偏动作: 结合策略失败报告和 branch ledger，选择下一轮 bounded branch experiment。
- 当前状态: 未修复

## promotion-gate | promote_candidate
- 摘要: Candidate failed the current promotion gate.
- 根因: 最大回撤 56.50% 高于 30.00%。
- 纠偏动作: 在下一次 promotion 前，先解决当前 gate 失败原因。
- 当前状态: 未修复

## promotion-gate | promote_candidate
- 摘要: Candidate failed the current promotion gate.
- 根因: 最大回撤 56.50% 高于 30.00%。；基准或等权基线不完整.
- 纠偏动作: 在下一次 promotion 前，先解决当前 gate 失败原因。
- 当前状态: 未修复

## 2026-03-26T02:03:48Z | promote_candidate
- 摘要: Promotion gate stayed blocked on the ready 492-name core snapshot.
- 根因: 最大回撤 56.50% 高于 30.00%。；基准或等权基线不完整 (`benchmark_missing:000001`).
- 纠偏动作: Trace why benchmark code `000001` is absent from the promotion close panel, then rerun promotion before opening drawdown-focused branch work.
- 当前状态: 未修复

## promotion-gate | promote_candidate
- 摘要: Candidate failed the current promotion gate.
- 根因: 最大回撤 56.50% 高于 30.00%。；基准或等权基线不完整.
- 纠偏动作: 在下一次 promotion 前，先解决当前 gate 失败原因。
- 当前状态: 未修复

## promotion-gate | promote_candidate
- 摘要: Candidate failed the current promotion gate.
- 根因: 最大回撤 56.50% 高于 30.00%。
- 纠偏动作: 在下一次 promotion 前，先解决当前 gate 失败原因。
- 当前状态: 未修复

## 2026-03-26T02:40:36 | as_share_research_v1-20260326T024036
- 摘要: 晋级门阻塞： 最大回撤 56.50% 高于 30.00%。
- 根因: 最大回撤 56.50% 高于 30.00%。
- 纠偏动作: Restore a usable frozen universe plus local bars before rerunning the dry-run cycle.
- 当前状态: 未修复

## promotion-gate | promote_candidate
- 摘要: Candidate failed the current promotion gate.
- 根因: 最大回撤 56.50% 高于 30.00%。
- 纠偏动作: 在下一次 promotion 前，先解决当前 gate 失败原因。
- 当前状态: 未修复

## 2026-03-26T02:44:04 | as_share_research_v1-20260326T024404
- 摘要: 晋级门阻塞： 最大回撤 56.50% 高于 30.00%。；基准或等权基线不完整.
- 根因: 最大回撤 56.50% 高于 30.00%。；基准或等权基线不完整.
- 纠偏动作: Restore a usable frozen universe plus local bars before rerunning the dry-run cycle.
- 当前状态: 未修复

## promotion-gate | promote_candidate
- 摘要: Candidate failed the current promotion gate.
- 根因: 最大回撤 56.50% 高于 30.00%。
- 纠偏动作: 在下一次 promotion 前，先解决当前 gate 失败原因。
- 当前状态: 未修复

## 2026-03-26T02:45:47 | as_share_research_v1-20260326T024547
- 摘要: 晋级门阻塞： 最大回撤 56.50% 高于 30.00%。
- 根因: 最大回撤 56.50% 高于 30.00%。
- 纠偏动作: Restore a usable frozen universe plus local bars before rerunning the dry-run cycle.
- 当前状态: 未修复

## 2026-03-26T02:45:47Z | benchmark-baseline-diagnosis
- 摘要: Benchmark baseline completeness was restored without changing equal-weight baseline semantics.
- 根因: `run_limit_up_backtest_artifacts` only loaded ranked codes into the strategy close panel, so benchmark code `000001` disappeared whenever it was not ranked.
- 纠偏动作: Keep the strategy close panel unchanged, but load a dedicated benchmark series and pass it into baseline evaluation for both `promote_candidate` and `agent_cycle`.
- 当前状态: 已修复

## 2026-03-26T03:29:38 | as_share_research_v1-20260326T032938
- 摘要: 晋级门阻塞： 最大回撤 56.50% 高于 30.00%。
- 根因: 最大回撤 56.50% 高于 30.00%。
- 纠偏动作: Restore a usable frozen universe plus local bars before rerunning the dry-run cycle.
- 当前状态: 未修复

## promotion-gate | promote_candidate
- 摘要: 当前候选仍被晋级门阻塞。
- 根因: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 纠偏动作: 拆解回撤究竟来自时间窗口集中、个股集中，还是持有尾部过长。
- 当前状态: 未修复

## promotion-gate | promote_candidate
- 摘要: 当前候选仍被晋级门阻塞。
- 根因: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 纠偏动作: 拆解回撤究竟来自时间窗口集中、个股集中，还是持有尾部过长。
- 当前状态: 未修复

## 2026-03-26T03:30:31+00:00 | as_share_research_v1-iterative-20260326T032946Z
- 摘要: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 根因: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 纠偏动作: 拆解回撤究竟来自时间窗口集中、个股集中，还是持有尾部过长。
- 当前状态: 未修复

## promotion-gate | promote_candidate
- 摘要: 当前候选仍被晋级门阻塞。
- 根因: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 纠偏动作: 拆解回撤究竟来自时间窗口集中、个股集中，还是持有尾部过长。
- 当前状态: 未修复

## 2026-03-26T03:46:08 | as_share_research_v1-20260326T034608
- 摘要: 晋级门阻塞： 最大回撤 56.50% 高于 30.00%。
- 根因: 最大回撤 56.50% 高于 30.00%。
- 纠偏动作: Restore a usable frozen universe plus local bars before rerunning the dry-run cycle.
- 当前状态: 未修复

## 2026-03-26T03:46:08+00:00 | as_share_research_v1-iterative-20260326T034540Z
- 摘要: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 根因: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 纠偏动作: 先对 `max_drawdown` 做更细的根因诊断，再决定是否进入下一轮 automation iteration。
- 当前状态: 未修复

## 2026-03-26T04:10:55 | as_share_research_v1-20260326T041055
- 摘要: 晋级门阻塞： 最大回撤 56.50% 高于 30.00%。
- 根因: 最大回撤 56.50% 高于 30.00%。
- 纠偏动作: Restore a usable frozen universe plus local bars before rerunning the dry-run cycle.
- 当前状态: 未修复

## 2026-03-26T04:15:27+00:00 | as_share_research_v1-iterative-20260326T041523Z
- 摘要: 最大回撤 56.50% 高于 30.00%。
- 根因: 最大回撤 56.50% 高于 30.00%。
- 纠偏动作: 恢复 frozen default universe 可用的 validated bar 快照。
- 当前状态: 未修复

## promotion-gate | promote_candidate
- 摘要: 当前候选仍被晋级门阻塞。
- 根因: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 纠偏动作: 拆解回撤究竟来自时间窗口集中、个股集中，还是持有尾部过长。
- 当前状态: 未修复

## promotion-gate | promote_candidate
- 摘要: 当前候选仍被晋级门阻塞。
- 根因: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 纠偏动作: 拆解回撤究竟来自时间窗口集中、个股集中，还是持有尾部过长。
- 当前状态: 未修复

## 2026-03-26T04:18:29+00:00 | as_share_research_v1-iterative-20260326T041803Z
- 摘要: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 根因: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 纠偏动作: 升级 blocker `max_drawdown`: 已停止自动重试，请收窄路径，并在下一次 run 前写回根因诊断。
- 当前状态: 未修复

## 2026-03-26T04:21:43 | as_share_research_v1-20260326T042143
- 摘要: 晋级门阻塞： 最大回撤 56.50% 高于 30.00%。
- 根因: 最大回撤 56.50% 高于 30.00%。
- 纠偏动作: Restore a usable frozen universe plus local bars before rerunning the dry-run cycle.
- 当前状态: 未修复

## promotion-gate | promote_candidate
- 摘要: 当前候选仍被晋级门阻塞。
- 根因: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 纠偏动作: 拆解回撤究竟来自时间窗口集中、个股集中，还是持有尾部过长。
- 当前状态: 未修复

## 2026-03-26T04:23:45+00:00 | as_share_research_v1-iterative-20260326T042319Z
- 摘要: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 根因: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 纠偏动作: 升级 blocker `max_drawdown`: 已停止自动重试，请收窄路径，并在下一次 run 前写回根因诊断。
- 当前状态: 未修复
