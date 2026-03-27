# Baseline Reset Note

## 为什么要重置 baseline
- 当前研究对象已经从旧 715 标的池切换为 `cn_a_mainboard_all_v1`
- 旧 universe 上的收益、回撤和分支优劣不能自动迁移到新 universe
- 如果不先重建 baseline，后续任何分支比较都会失真

## 哪些旧策略结论被降级
- `risk_constrained_limit_up`: 降级为 `legacy comparison only`
- `tighter_entry_limit_up`: 降级为 `legacy comparison only`
- 旧 universe 上的所有比较结论: 降级为 `historical comparison`

## 当前 active baseline 如何重建
1. 使用 `cn_a_mainboard_all_v1` 重建 security master 与 universe
2. 确认基础数据可拉取、清洗、验证
3. 先跑 `baseline_limit_up` 的最小重建验证
4. 只有 baseline 在新 universe 上建立后，再决定是否重新拉回其他分支

## 当前状态
- active baseline: `baseline_limit_up`
- baseline 状态: `baseline_reset_pending`
- 当前 blocker: coverage 仅 `51.11%`

## 当前结论边界
- baseline 重建已启动
- baseline 真值尚未建立
