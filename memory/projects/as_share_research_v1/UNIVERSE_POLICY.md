# Universe Policy

## Canonical Universe
- universe_id: `cn_a_mainboard_all_v1`
- canonical project: `as_share_research_v1`

## Inclusion Rules
- 只纳入上海主板 A 股普通股票
- 只纳入深圳主板 A 股普通股票
- 必须保留以下字段:
  - `exchange`
  - `board`
  - `security_type`
  - `share_class`
  - `security_name`
  - `is_st`
  - `st_label`

## Exclusion Rules
- 排除创业板
- 排除科创板
- 排除北交所
- 排除 ETF
- 排除 LOF
- 排除指数型证券 / 指数基金
- 排除 B 股
- 排除债券
- 排除可转债
- 排除其他非普通股票类证券

## ST Handling
- `ST` / `*ST` 只保留为标签
- 不是过滤条件
- 只要标的是沪深主板 A 股普通股票，即使为 `ST` / `*ST` 也保留在 universe 中

## Exchange / Board Interpretation
- `exchange=sse` 且 `board=mainboard` -> 上海主板
- `exchange=szse` 且 `board=mainboard` -> 深圳主板
- 其他 board 一律不进入 canonical universe

## Security Master Source Logic
- 首选交易所主数据:
  - 上交所 `主板A股`
  - 深交所 `A股列表` 且 `板块=主板`
- 统一转换为 security master 后，再按 metadata 过滤
- 不允许直接从旧 `symbols.csv` 修补出新的 canonical universe

## Fallback Classification Assumptions
- 如果 `security_master.csv` 缺失，但本地 `symbols.csv` 仍保留了可用 metadata，可临时作为 local metadata fallback
- 这个 fallback 只用于测试夹具或临时恢复，不改变 canonical project 必须优先使用交易所 security master 的原则
- 如果主数据缺失，允许从本地数据库代码和已有 universe 代码做 fallback
- fallback 只在 source 不可用时使用
- fallback 规则必须显式写入字段 `classification_method`
- fallback 只能推断:
  - `exchange`
  - `board`
  - `security_type=common_stock`
  - `share_class=a_share`
- fallback 不能把无法确认的标的直接混入 active universe

## Audit Requirement
- 每次重建 universe 后，必须同步更新 `UNIVERSE_AUDIT.md`
- active tracked memory 只能引用 `cn_a_mainboard_all_v1`
