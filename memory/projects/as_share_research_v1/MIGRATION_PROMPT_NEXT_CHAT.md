# 下一轮迁移提示

## 当前总任务
保持 Phase 1 Research OS 可复现，tracked memory 与诚实的 runtime artifacts 保持一致。

## 当前阶段
Phase 1 Research OS

## 项目身份
- canonical_project_id: as_share_research_v1
- legacy_project_aliases: 2026Q1_limit_up
- identity_notice: 历史项目名 2026Q1_limit_up 仅作为 legacy alias / 迁移记录保留，不再代表当前活跃项目。

## 当前 Repo / Branch / HEAD
- repo_root: C:\Users\asus\Documents\Projects\BackTest
- branch: main
- head: 6ca785f874b0537ebbab6015cef5be3e4fa7fb01

## 已确认事实
- tracked_memory_dir: C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1
- runtime_meta_dir: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta
- runtime_artifacts_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1
- current_blocker: 最大回撤 48.67% 高于 30.00%。
- canonical_truth_summary: 规范项目当前处于晋级受阻阶段，真实主阻塞是 最大回撤 48.67% 高于 30.00%。；旧的“缺 bars”叙事已转为历史路径。

## 当前研究对象
- current_research_stage: 晋级受阻
- current_round_type: 策略推进轮
- primary_strategies: f1_elasticnet_v1（F1 mainline）
- secondary_strategies: f2_structured_latent_factor_v1（F2 challenger）, risk_constrained_limit_up（?????）, tighter_entry_limit_up（???????）
- blocked_strategies: risk_constrained_limit_up（?????）, tighter_entry_limit_up（???????）
- rejected_strategies: r1_predictive_error_overlay_v2（R1.2 ??）, r1_predictive_error_overlay_v1（R1.1 ??）, legacy_single_branch（?????）
- promoted_strategies: 当前为空

## 未确认问题
- 当前尚未记录新的未确认问题。

## 最近关键失败
晋级门阻塞： 最大回撤 48.67% 高于 30.00%。

## 当前 blocker
最大回撤 48.67% 高于 30.00%。

## Subagent 状态
- configured_gate: OFF
- effective_gate_this_run: OFF
- gate_reason: F2.1 stayed in OFF mode because this round was a tightly coupled serial implementation.
- active: none
- blocked: none
- active_research: none
- active_infrastructure: none
- recent_transition: frontier_reselection_complete
- continue_using_subagents: 否

## 最近策略动作
- baseline_limit_up | subagent:sa-20260330085335516869-0399 | implementer task for baseline_limit_up | 结果：Implementer refreshed the experiment record for baseline_limit_up and linked it to the worker mesh. | 决策变化：更新该策略分支的候选证据，但尚未形成 verifier 级结论。
- risk_constrained_limit_up | subagent:sa-20260330085342433245-d8a4 | scout task for risk_constrained_limit_up | 结果：Scout wrote a branch-pool evidence report for risk_constrained_limit_up with 42 candidate codes. | 决策变化：更新该策略分支的候选证据，但尚未形成 verifier 级结论。
- risk_constrained_limit_up | subagent:sa-20260330085344061248-3900 | implementer task for risk_constrained_limit_up | 结果：Implementer refreshed the experiment record for risk_constrained_limit_up and linked it to the worker mesh. | 决策变化：更新该策略分支的候选证据，但尚未形成 verifier 级结论。
- tighter_entry_limit_up | subagent:sa-20260330085350977018-7783 | scout task for tighter_entry_limit_up | 结果：Scout wrote a branch-pool evidence report for tighter_entry_limit_up with 42 candidate codes. | 决策变化：更新该策略分支的候选证据，但尚未形成 verifier 级结论。
- tighter_entry_limit_up | subagent:sa-20260330085352697380-81de | implementer task for tighter_entry_limit_up | 结果：Implementer refreshed the experiment record for tighter_entry_limit_up and linked it to the worker mesh. | 决策变化：更新该策略分支的候选证据，但尚未形成 verifier 级结论。

## 策略快照
- 当前规范项目ID: as_share_research_v1
- 历史别名: 2026Q1_limit_up
- 当前研究阶段: 晋级受阻
- 当前轮次类型: 策略推进轮
- 当前主线策略: f1_elasticnet_v1（F1 mainline）
- 当前支线策略: f2_structured_latent_factor_v1（F2 challenger）, risk_constrained_limit_up（?????）, tighter_entry_limit_up（???????）
- 当前 blocked 策略: risk_constrained_limit_up（?????）, tighter_entry_limit_up（???????）
- 当前 rejected 策略: r1_predictive_error_overlay_v2（R1.2 ??）, r1_predictive_error_overlay_v1（R1.1 ??）, legacy_single_branch（?????）
- 当前 promoted 策略: 当前为空
- 系统推进判断: 本轮主要把当前研究结论、阻塞原因和后续验证顺序写清楚，没有新增宽泛系统扩张。
- 策略推进判断: 本轮围绕 f1_elasticnet_v1（F1 mainline） 继续收敛研究阻塞；当前最硬的限制仍是 最大回撤 48.67% 高于 30.00%。。
- 规范叙事结论: 规范项目当前处于晋级受阻阶段，真实主阻塞是 最大回撤 48.67% 高于 30.00%。；旧的“缺 bars”叙事已转为历史路径。

## 研究进度
- Data inputs: 起步，1/4。证据：默认项目数据状态：latest core pool `core-0536a20f13d1` stayed consistent through F2 verifier, audit, and Excel export.；未发现足够证据支持更高评分。
- Strategy integrity: 部分可用，2/4。证据：单一研究核心与契约护栏已存在；最近已验证能力：Tracked memory 已按计划刷新： as_share_research_v1: revalidate spec parity before any new alpha claim。
- Validation stack: 部分可用，2/4。证据：审计/泄漏/晋级框架存在；最近已验证能力：Tracked memory 已按计划刷新： as_share_research_v1: revalidate spec parity before any new alpha claim。
- Promotion readiness: 阻塞，1/4。证据：当前 blocker：最大回撤 48.67% 高于 30.00%。；研究输入仍不足以支撑晋级评估。
- Subagent effectiveness: 部分可用，2/4。证据：subagent 开关与收尾规则已可用，但本轮配置 gate=OFF、实际执行 gate=OFF；自动收尾 0 个。
- 总体轨迹: 阻塞
- 本轮增量: 无实质变化
- 当前 blocker: 最大回撤 48.67% 高于 30.00%。
- 下一里程碑: 恢复 frozen default universe 可用的 validated bar 快照。
- 置信度: 中

## 最近一次高阶迭代
- workflow_mode: campaign
- target_productive_minutes: 40
- max_runtime_mode: bounded
- iteration_count: 0
- target_iterations: 0
- max_iterations: 0
- substantive_action_count: 0 / 3
- effective_progress_count: 0
- clarify_only_iterations: 0 / 1
- controlled_refresh_count: 0 (run_start_read_count=0)
- stop_reason: task_completed
- direction_change: 否
- blocker_escalation: 是
- blocker_key: unknown (repeat_count=0, historical_count=0)
- last_classification: 尚未运行
- max_active_subagents: 0
- configured_subagent_gate: OFF
- effective_subagent_gate: OFF (blocked/retired/merged/archived=0/0/0/0)
- subagents_used: none
- subagent_reason: Completed one bounded frontier reselection round with three temporary scouts.
- auto_closed_subagents: none
- alternative_subagents: none
- 本轮完成: 未记录
- 本轮未完成: 未记录
- 下一步建议: Retain F1 as the mainline and run one more bounded F2.1 variant before any wider model search.

## 下一步唯一建议
恢复 frozen default universe 可用的 validated bar 快照。

## 避免重复犯错
- 不要把 durable memory 再挪回被忽略的 runtime 目录。
- 在 frozen universe 具备已验证 bars 前，不要信任 default project 的研究结论。

## 必要验证优先
- pytest tests/test_excel_export.py -q
- pytest tests/test_strategy_visibility.py tests/test_manifest_and_memory_writeback.py tests/test_strategy_spec_consistency.py tests/test_weekday_rebalance_contract.py tests/test_leakage_guards.py -q
- python -m quant_mvp excel_export --project as_share_research_v1
- python -m quant_mvp research_audit --project as_share_research_v1
- python -m quant_mvp agent_cycle --project as_share_research_v1 --dry-run

## 如果上下文变薄，先读这些文件
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\PROJECT_STATE.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\STRATEGY_BOARD.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\VERIFY_LAST.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\HANDOFF_NEXT_CHAT.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\RESEARCH_MEMORY.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\POSTMORTEMS.md

## Tracked Memory 位置
C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1

## Subagent 相关 tracked 文件
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\SUBAGENT_REGISTRY.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\SUBAGENT_LEDGER.jsonl

## Strategy 相关 tracked 文件
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\STRATEGY_BOARD.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\STRATEGY_CANDIDATES
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\RESEARCH_PROGRESS.md

## Runtime Artifacts 位置
- C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta
- C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1
- C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents

## 当前真实能力边界
研究输入与验证入口已就绪，当前已进入策略验证 / 晋级受阻阶段；真正卡住的是最大回撤仍高于 30%。
