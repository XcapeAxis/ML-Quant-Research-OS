# baseline_limit_up

- strategy_id: `baseline_limit_up`
- role: `active baseline`
- status: `baseline_reset_pending`
- current_truth_level: `pilot_only`
- why_active: 新 canonical universe 上需要先有一条可复跑的 baseline，对后续所有分支提供对照。
- why_not_truth_yet: 当前 canonical universe coverage 只有 `51.11%`，最小验证可跑通不等于结论成立。
- latest_minimal_run:
  - total_return: `7.834251`
  - annualized_return: `0.306932`
  - max_drawdown: `-0.464826`
  - sharpe_ratio: `0.826956`
  - rank_dates: `412`
  - rank_unique_codes: `509`
- blocker: 先补齐 bars，再谈 baseline 真值
- next_validation: `data_validate` 通过后重跑 baseline 最小重建
