# 最近验证快照

- head: 9efa25a06e8f7003fd30c868a09a45232883135e
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

## 高阶迭代摘要
- iteration_count: 1
- target_iterations: 3
- max_iterations: 5
- stop_reason: 同一 blocker 已升级且继续推进 ROI 很低，自动停止。
- direction_change: 否
- blocker_escalation: 是
- blocker_key: max_drawdown (repeat_count=4, historical_count=3)
- last_classification: blocker 已被澄清
- max_active_subagents: 0
- subagent_gate_mode: AUTO (blocked/retired/merged/archived=0/31/0/0)
- subagents_used: none
- subagent_reason: 任务广度尚未达到安全拆分的最低阈值。
- auto_closed_subagents: none
- alternative_subagents: none
- 本轮完成: 重复 blocker `max_drawdown` 并已停止自动重试。
- 本轮未完成: 最大回撤 50.44% 高于 30.00%。；基准或等权基线不完整.
- 下一步建议: 升级 blocker `max_drawdown`: 已停止自动重试，请收窄路径，并在下一次 run 前写回根因诊断。
