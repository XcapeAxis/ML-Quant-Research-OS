# 策略比较

| Universe | 策略 | 收益 | 回撤 | Sharpe | 样本行数 | Baseline 状态 | 晋级结果 |
|---|---|---:|---:|---:|---:|---|---|
| full_a_mainboard_incl_st | baseline_limit_up | 5.62% | 56.50% | -0.0675 | 2472 | pass | 未通过 |
| full_a_mainboard_incl_st | risk_constrained_limit_up | 175.94% | 47.29% | 0.2743 | 1648 | pass | 未通过 |
| full_a_mainboard_incl_st | tighter_entry_limit_up | 14.09% | 52.42% | -0.0399 | 2472 | pass | 未通过 |
| full_a_mainboard_ex_st | baseline_limit_up | 5.62% | 56.50% | -0.0675 | 2472 | pass | 未通过 |
| full_a_mainboard_ex_st | risk_constrained_limit_up | 175.94% | 47.29% | 0.2743 | 1648 | pass | 未通过 |
| full_a_mainboard_ex_st | tighter_entry_limit_up | 14.09% | 52.42% | -0.0399 | 2472 | pass | 未通过 |

## 当前建议
- 主线继续推进: `risk_constrained_limit_up`
- 对照线保留: `baseline_limit_up`
- 暂缓线: `tighter_entry_limit_up`
