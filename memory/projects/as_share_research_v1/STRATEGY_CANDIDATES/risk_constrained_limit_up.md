# risk_constrained_limit_up

- strategy_id: `risk_constrained_limit_up`
- role: `legacy comparison`
- status: `legacy_comparison_only`
- why_downgraded: 现有优劣判断来自旧 universe，不再代表当前 active truth。
- current_rule: 在 `baseline_limit_up` 完成新 universe baseline rebuild 前，不允许恢复为 active candidate。
- next_validation: 等新 baseline 建好后，再决定是否重新纳入 active 比较。
