# Baseline Reset Note

## 现在该怎么理解 baseline
- baseline reset 已经不再是 `pending`
- 当前应把 `baseline_limit_up` 理解为：`baseline_validation_ready`，并且已经在 canonical universe 上完成了第一次 bounded verifier 尝试
- 这次 verifier 没卡在缺 bars，而是卡在 `Rank dataframe is empty`

## 已经完成的事
- canonical universe 已切换到 `cn_a_mainboard_all_v1`
- 当前 canonical coverage 是 `3165 / 3193 = 0.9912`
- 当前 core pool 是 `492` 只股票
- `baseline_limit_up` 最近一次 branch pool 是 `42` 只股票

## 当前真正阻塞 baseline 的原因
- verifier 评估 baseline 分支时，又按 `top_pct_limit_up=0.1` 对这 42 只 branch pool 股票再筛一轮
- 这会把候选压到低于 `stock_num=6` 的可用门槛，最终 `rank dataframe` 为空
- 这是 branch 评估接口的问题，不是 canonical universe 还没恢复

## 这条记录要防止的旧误解
- 不要再把 baseline 写成 `baseline_reset_pending`
- 不要再把当前阶段写成 `pilot`
- 不要再用旧的 `51.11% coverage` 叙事描述当前 canonical 项目
- `risk_constrained_limit_up` 和 `tighter_entry_limit_up` 现在是 canonical 项目里的 challenger，不再属于旧的 baseline reset 待处理列表

## 下一步
1. 先统一 tracked memory 和相关测试
2. 修正 branch pool 进入正式 ranking 的契约
3. 重跑 `baseline_limit_up` 的 bounded verifier
4. baseline 重新跑通后，再比较两个 challenger 分支
