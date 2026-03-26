# 最近验证快照

- head: 71b9dd4195b58aebb48496b0097226cb0021dd99
- branch: main
- 通过命令:
  - python -m quant_mvp data_validate --project as_share_research_v1
- 失败命令:
  - 未记录
- 默认项目数据状态: 已就绪覆盖： 715/715 个标的具备已验证 bars (coverage_ratio=1.0000, raw_rows=1441021, cleaned_rows=1419045, validated_rows=1419045).
- 工程边界结论: 已执行已验证数据恢复、覆盖缺口分析与 readiness 写回。
- 研究边界结论: 当前已验证快照已满足 promotion-grade research 的前置条件。
- subagent_gate_mode: AUTO
- active_subagents: none
- blocked_subagents: none
- 最近 subagent 事件: iterative_relevance_review

## 研究进度
- Data inputs: 可进入验证，3/4。证据：默认项目数据状态：已就绪覆盖： 715/715 个标的具备已验证 bars (coverage_ratio=1.0000, raw_rows=1441021, cleaned_rows=1419045, validated_rows=1419045).；当前输入已可支撑本阶段验证。
- Strategy integrity: 部分可用，2/4。证据：单一研究核心与契约护栏已存在；最近已验证能力：晋级门诊断已生成并写入 runtime artifacts。。
- Validation stack: 可进入验证，3/4。证据：已记录通过命令 1 条；当前验证栈已可作用于本阶段真实输入。
- Promotion readiness: 当前阶段可运行，4/4。证据：输入与验证均已到位，当前阶段已接近可直接用于晋级决策。
- Subagent effectiveness: 部分可用，2/4。证据：治理与生命周期可用，但本轮保持有效 OFF；gate=AUTO，自动关停 0 个。
- 总体轨迹: 已收敛
- 本轮增量: 有改进
- 当前 blocker: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 下一里程碑: 升级 blocker `max_drawdown`: 已停止自动重试，请收窄路径，并在下一次 run 前写回根因诊断。
- 置信度: 中

## 高阶迭代摘要
- workflow_mode: campaign
- target_productive_minutes: 40
- max_runtime_mode: bounded
- iteration_count: 1
- target_iterations: 4
- max_iterations: 6
- substantive_action_count: 0 / 3
- effective_progress_count: 1
- clarify_only_iterations: 1 / 1
- controlled_refresh_count: 1 (run_start_read_count=7)
- stop_reason: 同一 blocker 已升级且继续推进 ROI 很低，自动停止。
- direction_change: 否
- blocker_escalation: 是
- blocker_key: max_drawdown (repeat_count=5, historical_count=4)
- last_classification: blocker 已被澄清
- max_active_subagents: 0
- subagent_gate_mode: AUTO (blocked/retired/merged/archived=0/31/0/0)
- subagents_used: none
- subagent_reason: 任务广度尚未达到安全拆分的最低阈值。
- auto_closed_subagents: none
- alternative_subagents: none
- 本轮完成: 推进执行队列：刷新晋级边界诊断
- 本轮未完成: 刷新 repo truth 与审计基线
- 下一步建议: 升级 blocker `max_drawdown`: 已停止自动重试，请收窄路径，并在下一次 run 前写回根因诊断。
