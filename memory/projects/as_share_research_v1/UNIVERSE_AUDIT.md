# Universe Audit

## 当前结果

| 项目 | 结果 |
|---|---|
| universe_id | `cn_a_mainboard_all_v1` |
| universe_size | `3193` |
| 上交所主板 | `1703` |
| 深交所主板 | `1490` |
| `ST` / `*ST` 数量 | `129` |
| security master 路径 | `data/projects/as_share_research_v1/meta/security_master.csv` |
| universe 代码路径 | `data/projects/as_share_research_v1/meta/universe_codes.txt` |

## 被排除的证券类型
- 创业板
- 科创板
- 北交所
- ETF
- LOF
- 指数型证券 / 指数基金
- B 股
- 债券
- 可转债
- 其他非普通股票类证券

## ST 处理审计
- `ST` / `*ST` 保留在 universe 中
- `is_st` 字段已写入
- `st_label` 字段已写入
- `security_name` 字段已写入

## 为什么它比旧 715 标的池更接近目标研究对象
- 它覆盖的是沪深主板全量普通 A 股，而不是一个历史缩窄样本
- 它按 metadata 明确排除了不属于研究对象的证券类型
- 它把 `ST` / `*ST` 从“过滤条件”纠正为“标签字段”
- 它让数据 coverage 问题暴露成真实研究前提问题，而不是继续被旧样本遮蔽

## 当前不足
- 当前数据 coverage 只有 `51.11%`
- baseline 只能算“已启动重建”，不能算“已建立真相”

## 证据来源
- `python scripts/steps/10_symbols.py`
- `data/projects/as_share_research_v1/meta/security_master.csv`
- `data/projects/as_share_research_v1/meta/universe_codes.txt`
