# 研究记忆

## 当前 canonical truth
- 当前活跃项目只有 `as_share_research_v1`
- `2026Q1_limit_up` 只保留为历史别名与归档参考
- 当前不是缺 bars
- 当前 promotion-stage blocker 是两件事:
- `baseline_limit_up` 主线最大回撤 `50.44%` 高于 `30.00%`
- 直接 `promote_candidate` 仍报告 `benchmark_missing:000001`

## 为什么说旧叙事已过时
- 旧叙事 A: “默认项目缺可用日频 bars”
- 新证据: `data_validate` 已确认 `715/715` validated symbols；`promote_candidate` 也把 research readiness 标成 `ready`
- 结论: A 不是当前 truth，只是旧项目名 `2026Q1_limit_up` 时代留下的历史路径

## 为什么旧的 dry-run 指标也不能当当前 truth
- `agent_cycle --dry-run` 的 evaluator 仍会产出一份旧路径结果，里面出现过 `56.50%` 与 baseline pass
- 同轮直接 `promote_candidate` 才是当前更贴近实际晋级门的结果，显示 `50.44%` drawdown 与 `benchmark_missing:000001`
- 当前统一口径: 把 dry-run evaluator 里的旧值降级为历史对照证据，把 direct promotion gate 结果作为当前 canonical blocker

## 长期事实
- 当前主线策略是 `baseline_limit_up`
- 当前支线策略是 `risk_constrained_limit_up`、`tighter_entry_limit_up`
- 当前 rejected track 是 `legacy_single_branch`
- 当前 subagent 配置开关是 `AUTO`，但本轮有效执行是 `OFF`

## 负面记忆
- 不要再把“缺 bars”写成 `as_share_research_v1` 的当前 blocker
- 不要再把 `2026Q1_limit_up` 当成当前活跃项目名
- 不要把 infrastructure-only 的整理工作写成新的策略研究结论
- 不要在没有解释 baseline 差异前，就把回撤问题简化成泛参数搜索

## 假设与未知项
- 已确认事实: 数据输入 ready，promotion-stage gate 失败
- 工作假设: 过高回撤主要来自时间窗口集中、个股集中，或持有尾部过长
- 未知项: 为什么 direct `promote_candidate` 仍报告 `benchmark_missing:000001`，而旧 dry-run evaluator 曾显示 baseline pass

## 下一步记忆
- 先拆清 `baseline_limit_up` 的回撤来源
- 再解释 direct `promote_candidate` 与旧 dry-run evaluator 的 baseline 差异
- 最后再决定优先验证 `risk_constrained_limit_up` 还是 `tighter_entry_limit_up`
