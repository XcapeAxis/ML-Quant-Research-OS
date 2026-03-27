# 下一轮迁移提示

## 当前任务
- 继续 `as_share_research_v1` 的 universe reset campaign，不要切 project id

## 当前真相
- canonical universe 已改为 `cn_a_mainboard_all_v1`
- 旧 715 标的池只保留为 legacy archive / historical comparison
- active baseline 仍在重建中，状态是 `baseline_reset_pending`
- `risk_constrained_limit_up` 与 `tighter_entry_limit_up` 现在只是 legacy comparison only

## 当前 blocker
- canonical universe coverage 只有 `51.11%`
- 没有完成 bars 补齐前，不要把任何策略结论当 active truth

## 下一步唯一优先动作
- 补齐 `cn_a_mainboard_all_v1` 缺失 bars，重跑 `data_validate`，再重跑 `baseline_limit_up`

## 迁移注意事项
- 不要重新启用旧 715 标的池作为默认输入
- 不要重新引入自动 shrink / refreeze 逻辑
- 不要把旧 universe 的比较结果写回 active memory
