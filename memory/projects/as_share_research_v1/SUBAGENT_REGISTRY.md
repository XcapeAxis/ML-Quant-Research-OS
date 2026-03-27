# Subagent 注册表

## 当前开关
- configured gate: AUTO
- effective gate this run: OFF
- 是否继续使用 subagents: 否
- 当前判断原因: 默认项目的数据 blocker 还没清掉，现在扩展多个 subagent 只会增加协作成本。
- 最近事件: 未记录

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
- data_steward: 负责数据提供商、拉取、清洗与覆盖诊断，但不改动策略逻辑。
- strategy_auditor: 检查策略入口、默认配置和文档是否与现状研究发生漂移。
- validation_guard: 负责泄漏、稳健性、baseline 和 promotion gate 的验证工作。
- memory_curator: 保持 tracked memory、handoff 和 migration prompt 简洁、准确。
- tooling_scout: 在增加任何东西前，先查缺失工具、policy 文件和可复现边界。
- integration_merger: 合并可兼容的工作流、减少重复，并关停已完成的临时 subagent。

## 实例记录
- 尚无已实例化 subagents
