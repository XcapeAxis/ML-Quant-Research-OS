# 研究推进

- 当前轮次类型: 基础设施恢复轮
- 系统推进: 本轮主要推进研究前提恢复、长期记忆写回和研究对象显式化。
- 策略推进: 本轮未进行实质策略研究，原因是 默认项目 2026Q1_limit_up 仍缺可用日频 bars，当前不能做新的策略验证。；当前先恢复研究前提并保持策略对象可见。
- 当前主线策略: baseline_limit_up（涨停主线基线分支）
- 当前 blocker: 默认项目 2026Q1_limit_up 仍缺可用日频 bars，当前不能做新的策略验证。
- 当前 blocked 策略: baseline_limit_up（涨停主线基线分支）, risk_constrained_limit_up（涨停主线风控分支）, tighter_entry_limit_up（涨停主线收紧入场分支）
- 当前 rejected 策略: legacy_single_branch（旧单分支兼容路径）
- 下一步建议: 先恢复 2026Q1_limit_up 可用日频 bars，再从 baseline_limit_up 开始第一轮 bounded validation。
