# 策略研究看板

## 当前 active baseline
| 策略 | 角色 | 状态 | 说明 |
|---|---|---|---|
| `baseline_limit_up` | active baseline | `baseline_validation_ready` | 已在 canonical universe 上完成最小重建与 readiness 复核，但仍不是 active truth。 |

## legacy comparison only
| 策略 | 当前地位 | 说明 |
|---|---|---|
| `risk_constrained_limit_up` | legacy comparison only | baseline 还没进入显式 `research-ready` promotion gate，不能恢复为主线。 |
| `tighter_entry_limit_up` | legacy comparison only | 同上，只保留后续对照资格。 |
| `legacy_single_branch` | archived reference | 旧 `715-symbol` 叙事只保留为迁移说明，不再进入 active path。 |

## 当前 blocker
- coverage stage: `validation-ready`
- canonical coverage: `3165 / 3193 = 99.12%`
- structural no-bars: `24`
- provider failures: `4`
- 当前不允许把 legacy 分支结论重新包装成 canonical universe 的真相
