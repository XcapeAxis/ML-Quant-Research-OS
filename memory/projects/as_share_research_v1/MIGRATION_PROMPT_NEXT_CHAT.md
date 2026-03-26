# 下一轮迁移提示

## 当前总任务
- 继续以 `as_share_research_v1` 作为唯一活跃项目，围绕 `baseline_limit_up` 的 promotion-stage failure 做下一步研究

## 当前阶段
- 晋级受阻

## 项目身份
- canonical active project id: `as_share_research_v1`
- legacy alias only: `2026Q1_limit_up`

## 当前研究对象
- 主线: `baseline_limit_up`
- 支线: `risk_constrained_limit_up`、`tighter_entry_limit_up`
- 阻塞: `baseline_limit_up`、`risk_constrained_limit_up`、`tighter_entry_limit_up`
- 拒绝: `legacy_single_branch`

## 当前 Repo / Branch / HEAD
- branch: `main`
- head: `0721bb172cd1bdc0ebfdd1d1477688d6c18c691a`

## 已确认事实
- 数据 ready，不再是缺 bars
- direct `promote_candidate` 的当前 blocker 是 `50.44%` drawdown 与 `benchmark_missing:000001`
- 旧 dry-run evaluator 的 `56.50%` / baseline pass 只保留为历史对照

## 未确认问题
- baseline 差异来源
- 回撤根因拆解结果

## 最近关键失败
- promotion gate 仍未通过

## 当前 blocker
- `baseline_limit_up` 最大回撤超阈值
- baseline 仍有直接 gate 差异待解释

## Subagent 状态
- configured gate: `AUTO`
- effective gate this run: `OFF`
- active strategy-research subagents: 无
- active infrastructure subagents: 无
- 当前正确做法: 先写清 blocker，再决定是否值得并行

## 最近策略动作
- 本轮无实质策略研究；只统一 canonical identity、blocker 叙事与动作可见性

## 下一步唯一建议
- 先解释 direct promotion gate 的 baseline 差异，并拆解主线回撤来源

## 避免重复犯错
- 不要把 `2026Q1_limit_up` 当当前项目
- 不要把缺 bars 当当前 blocker
- 不要把 infrastructure-only 工作写成策略推进

## 必要验证优先
- `promote_candidate`
- `data_validate`
- `research_audit`

## 如果上下文变薄，先读这些文件
- `PROJECT_STATE.md`
- `RESEARCH_MEMORY.md`
- `VERIFY_LAST.md`
- `STRATEGY_BOARD.md`
- `SUBAGENT_REGISTRY.md`

## Tracked Memory 位置
- `memory/projects/as_share_research_v1/`

## Strategy 相关 tracked 文件
- `STRATEGY_BOARD.md`
- `STRATEGY_ACTION_LOG.jsonl`
- `RESEARCH_ACTIVITY.md`
- `IDEA_BACKLOG.md`

## Runtime Artifacts 位置
- `artifacts/projects/as_share_research_v1/`
