# 失败复盘

## 2026-03-27 Canonical Coverage Gap
- 失败路径: universe reset 后没有补 missing-only bars，导致旧 DB 残留和新 canonical universe 混在一起。
- 根因: `bars_registry.json` 仍停在旧池子规模，coverage gap 大量落在 `raw_never_attempted`。
- 修复: 改为 missing-only incremental backfill，并把截止日后上市样本单独标记为结构性无 bars。
