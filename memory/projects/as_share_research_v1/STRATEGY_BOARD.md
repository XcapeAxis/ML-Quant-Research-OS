# 策略研究看板

## 当前 active truth

| 策略 | 角色 | 状态 | 说明 |
|---|---|---|---|
| `baseline_limit_up` | active baseline | `baseline_reset_pending` | 新 canonical universe 上已完成最小重建验证，但 coverage 仅 `51.11%`，还不能当稳定结论。 |

## legacy comparison only

| 策略 | 当前地位 | 说明 |
|---|---|---|
| `risk_constrained_limit_up` | legacy comparison only | 旧 universe 上的改进结论已降级，等待新 baseline 建好后再决定是否重新纳入 active 研究。 |
| `tighter_entry_limit_up` | legacy comparison only | 旧 universe 上的结论已降级，暂不作为当前真相。 |
| `legacy_single_branch` | archived | 仅保留历史记录，不再进入 active narrative。 |

## 当前 blocker
- data readiness 仍是主 blocker: `1632 / 3193 = 51.11%`
- promotion gate 不能代表策略失败或成功，只能说明新 universe 数据尚未补齐

## 当前研究判断
- 当前主线不是“旧 universe 下继续优化哪条策略”，而是“先在新 universe 上把 baseline 重建出来”。
- baseline 建好前，不允许把任何旧比较结果平移成当前 active 结论。

## 下一步
- 先补 bars
- 再重跑 `data_validate`
- 再重跑 `baseline_limit_up`
- 最后才决定是否重新拉回 `risk_constrained_limit_up` 和 `tighter_entry_limit_up`
