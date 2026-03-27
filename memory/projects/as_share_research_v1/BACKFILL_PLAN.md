# Incremental Backfill Plan

## 目标
- 只补当前 canonical universe 的缺失 bars，不重做 universe reset，不恢复旧 715-symbol pool。
- 优先补最影响研究客观性的缺口，先解决交易所偏差，再解决剩余个股缺口。

## 优先级
1. 沪市主板缺口优先，因为它是此前 51.11% coverage 的最大偏差源。
2. 截止日 `2025-07-01` 前已上市但仍缺 bars 的标的优先，因为它们理论上应该可回补。
3. 截止日后上市的新股单独归类为结构性无 bars，不计入 provider failure。

## 本轮执行
- 预估 backfill candidates: `4`
- 本轮实际选中: `4`
- 选中样例: `605296、605259、601665、601528`
- 本轮是否已执行: `True`

## Stop Condition
- 当 unexplained missing 不再以 `raw_never_attempted` 为主，且 coverage 至少进入 `validation-ready`。
- 若只剩 provider failure / provider empty / 截止日后上市三类缺口，则停止扩大 backfill 范围，转入重试和分类。

## 本轮结论
- 当前 stage: `validation-ready`
- provider attempt success: `0 / 4 = 0.00%`
