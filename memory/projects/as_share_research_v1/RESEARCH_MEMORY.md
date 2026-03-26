# 研究记忆

## 已确认事实
- `000001` 当前同时服务于 market stoploss 和 benchmark baseline，对应的是不同链路。
- `benchmark_missing:000001` 已定位为 diagnostic baseline 传参问题，不是数据库里缺 000001。
- 当前 canonical universe policy 已升级为双宇宙：研究基线含 ST，部署对照不含 ST。
- 但当前冻结 symbols 快照中的 ST 暴露为 0，所以本轮含 ST / 不含 ST 物化结果一致。

## 当前策略判断
- 主线继续推进: `risk_constrained_limit_up`
- 对照线: `baseline_limit_up`
- 暂缓线: `tighter_entry_limit_up`
- 当前主 blocker: drawdown，不再是 benchmark wiring。

## 负面记忆
- 不要再把当前 drawdown 问题解释成 000001 缺 bars。
- 不要把当前 ST 结论写成“已证明无影响”；当前只能说冻结源里 ST=0，尚未观测到 ST 效应。
- 不要在 universe 物化仍退化时，把 deployment control 的结果过度外推成真实全A部署结论。
