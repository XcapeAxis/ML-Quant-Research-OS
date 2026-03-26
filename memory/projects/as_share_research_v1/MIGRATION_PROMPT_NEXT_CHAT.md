# 下一轮迁移提示

## 当前总任务
保持 Phase 1 Research OS 可复现，tracked memory 与诚实的 runtime artifacts 保持一致。

## 当前阶段
Phase 1 Research OS

## 当前 Repo / Branch / HEAD
- repo_root: C:\Users\asus\Documents\Projects\BackTest
- branch: main
- head: 053e4159ecdc1f2b86633b366f2a01f2cea7d9a2

## 已确认事实
- tracked_memory_dir: C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1
- runtime_meta_dir: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta
- runtime_artifacts_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1
- current_blocker: 最大回撤 56.50% 高于 30.00%。

## 当前研究对象
- current_round_type: 策略推进轮
- primary_strategies: baseline_limit_up（涨停主线基线分支）
- secondary_strategies: risk_constrained_limit_up（涨停主线风控分支）, tighter_entry_limit_up（涨停主线收紧入场分支）
- blocked_strategies: baseline_limit_up（涨停主线基线分支）, risk_constrained_limit_up（涨停主线风控分支）, tighter_entry_limit_up（涨停主线收紧入场分支）
- rejected_strategies: legacy_single_branch（旧单分支兼容路径）
- promoted_strategies: 当前为空

## 未确认问题
- 当前尚未记录新的未确认问题。

## 最近关键失败
晋级门阻塞： 最大回撤 56.50% 高于 30.00%。

## 当前 blocker
最大回撤 56.50% 高于 30.00%。

## Subagent 状态
- gate_mode: AUTO
- active: none
- blocked: none
- active_research: none
- active_infrastructure: none
- recent_transition: 迭代相关性复核
- continue_using_subagents: 否

## 策略快照
- 当前轮次类型: 策略推进轮
- 当前主线策略: baseline_limit_up（涨停主线基线分支）
- 当前支线策略: risk_constrained_limit_up（涨停主线风控分支）, tighter_entry_limit_up（涨停主线收紧入场分支）
- 当前 blocked 策略: baseline_limit_up（涨停主线基线分支）, risk_constrained_limit_up（涨停主线风控分支）, tighter_entry_limit_up（涨停主线收紧入场分支）
- 当前 rejected 策略: legacy_single_branch（旧单分支兼容路径）
- 当前 promoted 策略: 当前为空
- 系统推进判断: 本轮主要刷新研究边界、验证状态和长期记忆，而不是继续扩张治理层。
- 策略推进判断: 本轮围绕 baseline_limit_up（涨停主线基线分支） 继续收敛研究 blocker；当前最硬的限制仍是 最大回撤 56.50% 高于 30.00%。。

## 研究进度
- Data inputs: 可进入验证，3/4。证据：默认项目数据状态：已就绪覆盖： 715/715 个标的具备已验证 bars (coverage_ratio=1.0000, raw_rows=1441021, cleaned_rows=1419045, validated_rows=1419045).；当前输入已可支撑本阶段验证。
- Strategy integrity: 部分可用，2/4。证据：单一研究核心与契约护栏已存在；最近已验证能力：Tracked memory 已按计划刷新： as_share_research_v1: revalidate spec parity before any new alpha claim。
- Validation stack: 可进入验证，3/4。证据：已记录通过命令 1 条；当前验证栈已可作用于本阶段真实输入。
- Promotion readiness: 当前阶段可运行，4/4。证据：输入与验证均已到位，当前阶段已接近可直接用于晋级决策。
- Subagent effectiveness: 部分可用，2/4。证据：治理与生命周期可用，但本轮保持有效 OFF；gate=AUTO，自动关停 0 个。
- 总体轨迹: 阻塞
- 本轮增量: 无实质变化
- 当前 blocker: 最大回撤 56.50% 高于 30.00%。
- 下一里程碑: 恢复 frozen default universe 可用的 validated bar 快照。
- 置信度: 中

## 最近一次高阶迭代
- workflow_mode: campaign
- target_productive_minutes: 40
- max_runtime_mode: bounded
- iteration_count: 3
- target_iterations: 4
- max_iterations: 6
- substantive_action_count: 2 / 3
- effective_progress_count: 2
- clarify_only_iterations: 0 / 1
- controlled_refresh_count: 3 (run_start_read_count=7)
- stop_reason: 同一 blocker 已升级且继续推进 ROI 很低，自动停止。
- direction_change: 是
- blocker_escalation: 是
- blocker_key: max_drawdown (repeat_count=7, historical_count=5)
- last_classification: 没有显著进展
- max_active_subagents: 0
- subagent_gate_mode: AUTO (blocked/retired/merged/archived=0/31/0/0)
- subagents_used: none
- subagent_reason: 任务广度尚未达到安全拆分的最低阈值。
- auto_closed_subagents: none
- alternative_subagents: none
- 本轮完成: 推进执行队列：恢复默认项目可用日频 bars、刷新晋级边界诊断、跑一次 dry-run control plane
- 本轮未完成: 刷新 repo truth 与审计基线
- 下一步建议: 升级 blocker `max_drawdown`: 已停止自动重试，请收窄路径，并在下一次 run 前写回根因诊断。

## 下一步唯一建议
恢复 frozen default universe 可用的 validated bar 快照。

## 避免重复犯错
- 不要把 durable memory 再挪回被忽略的 runtime 目录。
- 在 frozen universe 具备已验证 bars 前，不要信任 default project 的研究结论。

## 必要验证优先
- python -m quant_mvp data_validate --project as_share_research_v1

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
工程护栏可用，但真实 default project 研究仍被数据覆盖率阻塞。
