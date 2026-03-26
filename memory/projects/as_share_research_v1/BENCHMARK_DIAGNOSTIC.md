# Benchmark 诊断

- benchmark_code: `000001`
- calendar_code: `000001`
- close_panel_has_benchmark: `False`
- benchmark_series_len: `2051`
- implicit_status: `degraded`
- explicit_status: `pass`

## 000001 当前角色
- 作为 calendar_code，000001 提供市场止损过滤输入。
- 作为 baselines.benchmark_code，000001 提供晋级对照基准。
- 000001 不需要出现在策略 rank 的 close_panel 中；显式传入 benchmark_series 即可。

## 本轮关键证据
- 不显式传入 benchmark_series 时：`degraded`，原因：benchmark_missing:000001`
- 显式传入 benchmark_series 后：`pass`，原因：无`
- drawdown 结论强度：当前 56.50% 的回撤结论可作为策略自身结果看待；先前需要降级的是 benchmark 链路解释，不是策略净值本身。

## 研究结论
- `benchmark_missing:000001` 已定位为基准链路传参问题，而不是数据库里真的缺 000001。
