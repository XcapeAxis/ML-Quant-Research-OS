# 项目状态

## 当前总任务
- canonical project: `as_share_research_v1`
- canonical universe: `cn_a_mainboard_all_v1`
- 当前阶段: `universe reset / baseline rebuild`
- 当前主问题: 旧 715 标的池已经退出 active path，但新 canonical universe 的数据覆盖率只有 `1632 / 3193 = 51.11%`，还不足以把任何策略结论当成当前真相。

## 当前真相
- 当前 active research universe 只允许使用沪深主板 A 股普通股票。
- 创业板、科创板、北交所、ETF、LOF、指数型证券、B 股、债券、可转债和其他非普通股票类证券均排除在 active universe 外。
- `ST` / `*ST` 只保留为标签，不再作为 universe 过滤条件。
- 旧 715 标的池已归档到 `data/projects/as_share_research_v1/meta/legacy_universe/`，仅允许用于历史对照或迁移说明。
- 当前 active baseline 不是旧池子的回放结果，而是新 universe 上的 `baseline_limit_up` 重建流程。

## 当前数据状态
- security master 已重建: `data/projects/as_share_research_v1/meta/security_master.csv`
- 当前 universe 规模: `3193`
- 上交所主板: `1703`
- 深交所主板: `1490`
- `ST` / `*ST` 数量: `129`
- 最新稳定 readiness 结论: `pilot`
- 最新稳定 coverage ratio: `51.11%`

## 当前策略状态
- active baseline track: `baseline_limit_up`
- active baseline 状态: `baseline_reset_pending`
- legacy comparison only: `risk_constrained_limit_up`
- legacy comparison only: `tighter_entry_limit_up`
- archived strategy track: `legacy_single_branch`

## 回归观察名单
- `scripts/steps/10_symbols.py` 是否只生成沪深主板 A 股
- `data/projects/as_share_research_v1/meta/universe_codes.txt` 是否与 security master 一致
- `quant_mvp/universe_profiles.py` 是否继续按 metadata 过滤 universe
- `quant_mvp/data/coverage_gap.py` 是否禁止自动 shrink canonical universe
- `STRATEGY_BOARD.md` / `RESEARCH_MEMORY.md` / `VERIFY_LAST.md` 是否仍把旧池子结论当 active truth
- `baseline_limit_up` 是否仍被错误写成“已验证主线”

## Evidence Ledger
- 已确认: 新 security master 已生成，`universe_id=cn_a_mainboard_all_v1`，规模 `3193`。
- 已确认: `ST` / `*ST` 已改成标签字段，未再作为过滤条件。
- 已确认: data validate 的稳定检查显示 coverage 仅 `51.11%`，readiness 仍为 `pilot`。
- 已确认: baseline 最小重建验证已跑通，但只覆盖部分 canonical universe，不能当 active truth。

## Decision Ledger
- 选择保留 `as_share_research_v1` 作为唯一 canonical project，不再切换 project id。
- 选择废弃旧 715 标的池的 active 地位，因为它与“沪深主板全量 A 股”研究对象不一致。
- 选择把 `baseline_limit_up` 设为当前唯一 active baseline track，因为新 universe 上还没有完成可晋级结论。
- 暂不重新启用 `risk_constrained_limit_up` 与 `tighter_entry_limit_up` 的 active 结论，因为它们仍缺少新 universe 上的 baseline 对照。

## 下一步唯一最高优先动作
- 继续补齐 `cn_a_mainboard_all_v1` 缺失 bars，随后重跑 `data_validate` 和 `baseline_limit_up` 最小重建验证。
