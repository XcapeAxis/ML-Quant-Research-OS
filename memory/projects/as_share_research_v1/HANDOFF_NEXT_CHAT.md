# 下一轮交接

## 当前总任务
- 保持 `as_share_research_v1` 作为唯一活跃项目名，并继续围绕 `baseline_limit_up` 的 promotion-stage blocker 做下一步验证

## 当前阶段
- 晋级受阻

## 项目身份
- 规范项目ID: `as_share_research_v1`
- 历史别名: `2026Q1_limit_up`
- 使用规则: 旧项目名只允许出现在归档说明和历史引用里，不能再当当前默认项目

## 当前研究对象
- 主线: `baseline_limit_up`
- 支线: `risk_constrained_limit_up`、`tighter_entry_limit_up`
- 阻塞: `baseline_limit_up`、`risk_constrained_limit_up`、`tighter_entry_limit_up`
- 拒绝: `legacy_single_branch`

## 当前 Repo / Branch / HEAD
- branch: `main`
- head: `0721bb172cd1bdc0ebfdd1d1477688d6c18c691a`

## 已确认事实
- `data_validate` 已确认 `715/715` validated symbols，当前不是缺 bars
- 直接 `promote_candidate` 的当前结果是 `50.44%` drawdown 和 `benchmark_missing:000001`
- 旧 dry-run evaluator 里的 `56.50%` / baseline pass 只保留为历史对照，不再代表当前 canonical truth
- 本轮未推进实质策略研究，只完成项目身份、blocker 叙事、策略动作可见性与 subagent 说明清理

## 未确认问题
- 为什么 direct `promote_candidate` 仍报告 `benchmark_missing:000001`
- 回撤主要来自时间窗口集中、个股集中，还是持有尾部过长

## 最近关键失败
- promotion gate 仍失败，原因是 `baseline_limit_up` 回撤超阈值

## 当前 blocker
- `baseline_limit_up` 最大回撤 `50.44% > 30.00%`
- 直接 `promote_candidate` 同时报告 `benchmark_missing:000001`

## Subagent 状态
- configured gate: `AUTO`
- effective gate this run: `OFF`
- active strategy-research subagents: 无
- active infrastructure subagents: 无
- 原因: 当前任务仍是一个需要先写清楚的单一路径 blocker

## 当前 active 研究型 subagents
- 无

## 最近策略动作
- 本轮无实质策略研究；只统一 canonical 项目身份、blocker 叙事与动作可见性

## 下一步唯一建议
- 先拆解 `baseline_limit_up` 的回撤来源，并解释 direct promotion gate 的 baseline 差异，再决定优先验证哪条支线

## 避免重复犯错
- 不要再把“缺 bars”写成当前 blocker
- 不要再把 `2026Q1_limit_up` 当成当前活跃项目名
- 不要把基础设施整理写成新的策略验证结论

## 必要验证优先
- direct `promote_candidate`
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

## 最近一次高阶迭代
- 历史 last loop 仍显示 `low_roi_repeated_blocker`
- 当前应把它当作“旧自动化轨迹”，不要覆盖当前 canonical truth
