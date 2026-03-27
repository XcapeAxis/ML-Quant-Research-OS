# 研究记忆

## 已确认事实
- canonical project 继续保持 `as_share_research_v1`
- canonical universe 继续保持 `cn_a_mainboard_all_v1`
- 当前 coverage 已从 `51.11%` 修复到 `99.12%`
- eligible coverage 已到 `99.87%`
- ST 总数 `129`，已有 bars 的 ST 数量也是 `129`
- 当前剩余缺口只有两类: `24` 个截止日后上市新股，`4` 个 provider failure

## 关键判断
- 旧的 51.11% coverage 不是随机缺失，主偏差来自沪市主板长期未回补
- 当前 pilot 对 ST / 非 ST 不再有明显偏差，主要偏差已转成“新股结构性无 bars + 少数 provider failure”
- baseline 现在只能解释为 `baseline_validation_ready`
- legacy 分支还不能恢复为当前 active truth

## 负面记忆
- 不要重做 universe reset
- 不要恢复旧 `715-symbol pool`
- 不要把 `ST` 误当成 coverage gap 的主因
- 不要把底层 `research_readiness.stage=ready` 误读成 campaign `research-ready`
- 不要因为 coverage 已经超过 99% 就提前恢复 legacy 主线

## 当前未知项
- `605296`、`605259`、`601665`、`601528` 是暂时 provider 失败还是可稳定复现的个案异常
