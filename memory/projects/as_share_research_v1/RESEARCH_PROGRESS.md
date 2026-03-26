# 研究进度

| 维度 | 状态 | 分数 | 证据 |
|---|---|---:|---|
| 数据输入 | 可进入验证 | 3/4 | `data_validate` 确认 `715/715` validated symbols |
| 策略完整性 | 部分可用 | 2/4 | 主线 / 支线 / rejected track 已明确，但回撤根因尚未拆清 |
| 验证层 | 可进入验证 | 3/4 | `research_audit`、`agent_cycle --dry-run`、`promote_candidate`、verify snapshot 已重跑 |
| 晋级准备度 | 受阻 | 2/4 | 直接 `promote_candidate` 报告 `50.44%` drawdown 和 `benchmark_missing:000001` |
| Subagent 有效性 | 部分可用 | 2/4 | configured gate=`AUTO`，effective gate=`OFF`，当前没有值得并行拆分的分支 |

- 总体轨迹: 阻塞
- 本轮增量: 无新增策略结论，但 canonical story 已统一
- 当前 blocker: `baseline_limit_up` 最大回撤超阈值，且 baseline 仍有差异待解释
- 下一里程碑: 完成回撤来源拆解，并解释 direct gate 的 baseline 差异
