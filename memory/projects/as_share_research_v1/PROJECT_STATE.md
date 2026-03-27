# 项目状态

## 当前总任务
- canonical project: `as_share_research_v1`
- canonical universe: `cn_a_mainboard_all_v1`
- 当前阶段: `Canonical Universe Coverage Recovery`
- 当前 readiness: `validation-ready`

## 当前真相
- 当前 coverage: `3165 / 3193 = 99.12%`
- eligible coverage（剔除 `2025-07-01` 后上市）: `3165 / 3169 = 99.87%`
- ST 覆盖: `129 / 129 = 100.00%`
- 剩余缺口: `28`
- 其中结构性无 bars: `24`
- 其中 provider failure: `4`
- baseline 当前状态: `baseline_validation_ready`

## 回归观察名单
- canonical universe 必须继续保持 `cn_a_mainboard_all_v1`
- `ST` 只能作为标签，不能回退成过滤条件
- `risk_constrained_limit_up` / `tighter_entry_limit_up` 继续保持 `legacy comparison only`
- 4 个 provider failure 是否在后续重试后清零或被稳定分类
- `research_readiness.json` 里的底层 `ready` 只代表数据闸门通过，不能替代 campaign stage

## Evidence Ledger
- 旧真相: `1632 / 3193 = 51.11%`，主偏差集中在沪市主板 `600/601/603`
- 本轮回补后: `3165 / 3193 = 99.12%`
- 缺失分层: `24` 个截止日后上市新股 + `4` 个 provider failure
- provider 可恢复样本成功率: `967 / 971 = 99.59%`
- 当前 4 个失败代码: `605296`、`605259`、`601665`、`601528`

## Decision Ledger
- 选择 missing-only incremental backfill，而不是重拉全 universe
- 选择把 `2025-07-01` 后上市样本归类为结构性无 bars，而不是算 provider failure
- 选择把当前阶段定为 `validation-ready`，不自动晋级 `research-ready`
- 选择把 baseline 解释为 `baseline_validation_ready`，不是 active truth
- 继续冻结 legacy 主线，直到 baseline 经过后续显式 promotion gate

## 下一步唯一最高优先动作
- 只重试并分类 4 个 provider failure；在它们没有稳定结论前，不恢复任何 legacy 策略结论
