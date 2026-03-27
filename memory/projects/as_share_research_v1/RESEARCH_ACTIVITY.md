# 研究活动记录

| 时间 | 策略 | 执行者 | 动作 | 结果 | 决策变化 |
|---|---|---|---|---|---|
| 2026-03-27T11:21:44+08:00 | `__universe__` | `main:automated-integration-v1` | 重建 security master 与 canonical universe | 生成 `cn_a_mainboard_all_v1`，规模 `3193` | 旧 715 标的池退出 active path |
| 2026-03-27T11:32:43+08:00 | `__data__` | `main:automated-integration-v1` | 检查 canonical universe 数据覆盖 | 稳定 coverage `51.11%`，readiness `pilot` | baseline 只能进入 reset pending |
| 2026-03-27T11:40:00+08:00 | `baseline_limit_up` | `main:automated-integration-v1` | 跑新 universe 最小 baseline 重建验证 | 流程可跑通，但只具 pilot 级别证据 | 保留为唯一 active baseline track |
| 2026-03-27T11:45:00+08:00 | `risk_constrained_limit_up` | `main:automated-integration-v1` | 重置策略地位 | 旧结论降级为 legacy comparison only | 退出 active truth |
| 2026-03-27T11:45:00+08:00 | `tighter_entry_limit_up` | `main:automated-integration-v1` | 重置策略地位 | 旧结论降级为 legacy comparison only | 退出 active truth |
