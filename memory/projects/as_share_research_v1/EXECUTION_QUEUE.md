# 执行队列

| 任务ID | 标题 | 影响 | 风险 | 前置条件 | 当前状态 | Owner | 成功条件 | 停止条件 |
|---|---|---|---|---|---|---|---|---|
| recover_daily_bars | 恢复默认项目可用日频 bars | 高 | 低 | 无 | 就绪 | main | `data_validate` 后 blocker 缩小或 `data_ready=True`。 | full refresh 后仍无新证据且 blocker 未缩小。 |
| refresh_research_audit | 刷新 repo truth 与审计基线 | 中 | 低 | 以当前 blocker 重新确认 repo truth。 | 待排队 | main | 审计结果让下一轮选择更确定。 | 审计结果没有带来新的边界信息。 |
| refresh_promotion_boundary | 刷新晋级边界诊断 | 高 | 中 | 默认项目具备可研究输入。 | 阻塞 | main | promotion 失败边界被重新确认或收窄。 | 输入仍不足，继续执行 ROI 过低。 |
| dry_run_agent_cycle | 跑一次 dry-run control plane | 中 | 中 | 默认项目具备可研究输入。 | 阻塞 | main | dry-run 结果带来新的候选或 blocker 收敛。 | dry-run 只重复旧 blocker 且没有新信息。 |
