# 下一轮交接

## 当前总任务
- 保持 `as_share_research_v1` 不变
- 只围绕 `cn_a_mainboard_all_v1` 重建 active research baseline

## 一眼先看懂
- 旧 715 标的池已经放弃，不再是 active path
- 新 canonical universe 已建立，但数据覆盖率只有 `51.11%`
- 当前没有任何策略可以被当成新 universe 上的 active truth
- 当前唯一 active baseline track 是 `baseline_limit_up`

## 当前阶段
- `universe reset / baseline rebuild`

## 当前 blocker
- 缺失 canonical universe bars 太多，readiness 仍是 `pilot`

## 当前策略状态
- active baseline: `baseline_limit_up` -> `baseline_reset_pending`
- legacy comparison only: `risk_constrained_limit_up`
- legacy comparison only: `tighter_entry_limit_up`

## 下一步唯一动作
- 优先补齐 `cn_a_mainboard_all_v1` 缺失 bars，然后重跑 `data_validate` 和 `baseline_limit_up`

## 先读这些文件
- `memory/projects/as_share_research_v1/PROJECT_STATE.md`
- `memory/projects/as_share_research_v1/UNIVERSE_POLICY.md`
- `memory/projects/as_share_research_v1/UNIVERSE_AUDIT.md`
- `memory/projects/as_share_research_v1/BASELINE_RESET_NOTE.md`
- `memory/projects/as_share_research_v1/VERIFY_LAST.md`
