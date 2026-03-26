# 策略研究看板

## 0. 候选准入规则
- 原始想法先写入 [`IDEA_BACKLOG.md`](./IDEA_BACKLOG.md)
- 只有同时写清楚具体假设、经济含义、所需数据、下一步验证，才允许进入 `STRATEGY_CANDIDATES/`
- 被拒绝或暂缓的想法必须留痕，不允许为了“看板好看”而直接消失

## 1. 主线策略（Primary track）
- `baseline_limit_up`
- 当前状态: blocked
- 当前结论: 数据输入 ready，但 promotion-stage gate 失败
- 当前 blocker: 最大回撤 `50.44%` 高于 `30.00%`，且 direct `promote_candidate` 仍报告 `benchmark_missing:000001`
- 本轮变化: 无新增策略验证；只统一 canonical 项目身份、blocker 叙事、动作可见性

## 2. 支线策略（Secondary track）
- `risk_constrained_limit_up`
- 当前状态: blocked
- 当前原因: 先要拆清 `baseline_limit_up` 的回撤来源，再决定是否优先验证
- `tighter_entry_limit_up`
- 当前状态: blocked
- 当前原因: 同上

## 3. Blocked 策略
- `baseline_limit_up`
- `risk_constrained_limit_up`
- `tighter_entry_limit_up`

## 4. Rejected / Killed 策略
- `legacy_single_branch`
- 当前状态: rejected / archived
- 说明: 只保留历史记录，不再代表当前活跃研究路径

## 5. Promoted 策略
- 当前为空

## 6. 当前研究总判断
- 当前规范项目: `as_share_research_v1`
- 历史别名: `2026Q1_limit_up`
- 当前系统推进: 本轮只做 canonicalization、visibility、reporting cleanup
- 当前策略推进: 本轮没有新增策略研究结论；当前真实 blocker 已统一为 promotion-stage failure，而不是缺 bars
- 当前证据入口:
- [`STRATEGY_ACTION_LOG.jsonl`](./STRATEGY_ACTION_LOG.jsonl)
- [`RESEARCH_ACTIVITY.md`](./RESEARCH_ACTIVITY.md)
- [`IDEA_BACKLOG.md`](./IDEA_BACKLOG.md)
