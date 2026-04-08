# Subagent 注册表

## 当前开关
- configured gate: AUTO
- effective gate this run: OFF
- 是否继续使用 subagents: no
- 当前判断原因: 默认项目的数据 blocker 还没清掉，现在扩展多个 subagent 只会增加协作成本。
- 最近事件: none recorded

## 当前集合
- 当前 active 实例: none
- 当前 blocked 实例: none
- 已退役: none
- 已合并: none
- 已归档: none
- 已取消: none
- 已重构: none
- 临时实例: none
- 长生命周期模板: none
- 当前 active 研究型: none
- 当前 active 基础设施型: none

## 本轮判断
- 建议数量: 0
- 建议角色: none
- 不拆分原因: 当前默认项目的 blocker 还不值得为它再加一层协作开销。
- 计划理由: 在可用 validated bars 恢复前，subagent 保持有效 OFF，先不要拆分。

## 角色模板
- data_steward: Own provider, ingestion, cleaning, and data coverage diagnostics without changing strategy logic.
- strategy_auditor: Check strategy entrypoints, defaults, and documentation for drift.
- validation_guard: Own leakage, robustness, baseline, and promotion-gate verification work.
- memory_curator: Keep tracked memory, handoff, and migration prompts concise and accurate.
- tooling_scout: Investigate missing tools, policy files, and reproducibility boundaries before anything is added.
- integration_merger: Merge compatible workstreams, reduce overlap, and close out temporary subagents.

## 实例记录
- 尚无已实例化 subagents
