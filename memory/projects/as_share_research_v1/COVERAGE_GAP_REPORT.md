# Canonical Universe Coverage Gap Report

## 当前结论
- 当前 canonical universe: `cn_a_mainboard_all_v1`
- 当前阶段判断: `validation-ready`
- 当前 coverage: `3165 / 3193 = 99.12%`
- 可解释的结构性无 bars: `24`（截止日 `2025-07-01` 之后上市）
- 当前缺失不是随机缺失。最集中的缺口仍看交易所/代码段，而不是 ST 标签。
- 最大缺口代码段: `603(12)、001(9)、601(4)、605(2)、600(1)`

## 缺失最集中在哪
| 维度 | Universe | Covered | Missing | Coverage |
|---|---|---|---|---|
| SSE | 1703 | 1684 | 19 | 98.88% |
| SZSE | 1490 | 1481 | 9 | 99.40% |

| 上市年龄 | Universe | Covered | Missing | Coverage |
|---|---|---|---|---|
| 截止日后上市 | 24 | 0 | 24 | 0.00% |
| 3-8年 | 583 | 579 | 4 | 99.31% |
| 15年以上 | 1610 | 1610 | 0 | 100.00% |
| 8-15年 | 834 | 834 | 0 | 100.00% |
| 1-3年 | 111 | 111 | 0 | 100.00% |
| 1年内 | 31 | 31 | 0 | 100.00% |

## raw / cleaned / validated 缺口位置
- validated_covered: `3165`
- raw_never_attempted: `0`
- provider_failed: `4`
- provider_empty: `0`
- cleaned_or_validated_gap: `0`
- time_range_structural: `24`

## 直白判断
- 缺失不是随机缺失。
- 真正的系统性偏差先前主要是沪市主板 coverage 明显不足。
- ST 本身不是主要缺口来源；此前把 ST 当作过滤条件会误判问题，但当前 canonical universe 已经没有这么做。
- 样本偏差风险此前主要体现在：pilot 结果被深市/已存在历史 bars 的样本主导，不能代表整个主板 universe。
