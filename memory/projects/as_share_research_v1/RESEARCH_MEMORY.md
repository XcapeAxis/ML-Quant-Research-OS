# 研究记忆

## 已确认事实
- 当前 canonical project 仍是 `as_share_research_v1`。
- 当前 canonical universe 是 `cn_a_mainboard_all_v1`。
- 新 universe 由交易所主数据重建，不再从旧 `symbols.csv` 修修补补。
- 当前 universe 只包含上海主板 A 股与深圳主板 A 股普通股票。
- `ST` / `*ST` 只保留标签字段，不再作为过滤条件。
- 旧 715 标的池已退出 active input path，只能作为 legacy archive 或历史比较。

## 为什么旧 715 结论不能继续当 active truth
- 旧池子不是“沪深主板全量 A 股”对象，只是历史阶段留下的缩窄样本。
- 旧池子上的策略比较结果无法代表新 canonical universe 的整体表现。
- 旧池子会误导当前 baseline、promotion gate 和 data coverage 叙事。

## 当前新 universe 的意义
- 它把研究对象重新对齐到真实问题: 沪深主板 A 股全量研究，而不是旧样本优化。
- 它让 universe inclusion / exclusion / ST policy 都能被审计和测试。
- 它把数据缺口暴露成真实 blocker，而不是继续让旧样本掩盖 coverage 不足。

## 工作假设
- 在 canonical universe bars 补齐前，任何策略优劣都只能算暂时观察，不算 active truth。
- `baseline_limit_up` 仍适合做新 universe 的第一个 baseline，但必须先完成最小重建验证。
- `risk_constrained_limit_up` 与 `tighter_entry_limit_up` 只有在新 baseline 建好后，才值得重新比较。

## 未知项
- 剩余缺失 bars 的恢复速度与网络稳定性。
- 新 universe 全量覆盖后，`baseline_limit_up` 的回撤和收益会如何变化。
- `ST` 标签在全量主板样本里是否会改变策略特征分布。

## 负面记忆
- 不要再把旧 715 标的池上的收益/回撤比较当作当前主线结论。
- 不要在 readiness 仍是 `pilot` 时宣布任何策略“已验证”。
- 不要为了快速推进而重新允许 universe shrink 或 refreeze 成旧样本。

## 当前结论
- 本轮完成的是研究对象纠偏和 baseline 重置，不是策略优选定论。
