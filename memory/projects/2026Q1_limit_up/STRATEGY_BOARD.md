# 策略研究看板

## 1. 主线策略（Primary track）
- `baseline_limit_up` | 涨停主线基线分支 | stage=data-blocked | decision=blocked | 假设：过去一段时间反复出现涨停、随后回到突破起点附近的主板个股，后续更容易再次走强；先把这条主线稳定保存成基线，再评估其它改法。

## 2. 次级策略（Secondary track）
- `risk_constrained_limit_up` | 涨停主线风控分支 | stage=data-blocked | decision=blocked | 假设：在不破坏涨停回踩再启动这个主线定义的前提下，更严格的止损、市场过滤或持仓约束可以显著降低回撤。
- `tighter_entry_limit_up` | 涨停主线收紧入场分支 | stage=data-blocked | decision=blocked | 假设：把入选阈值收紧，只保留更接近再次启动位置的个股，可以减少过早买入带来的假突破和大回撤。

## 3. Blocked 策略
- `baseline_limit_up` | 涨停主线基线分支 | stage=data-blocked | decision=blocked | 假设：过去一段时间反复出现涨停、随后回到突破起点附近的主板个股，后续更容易再次走强；先把这条主线稳定保存成基线，再评估其它改法。
- `risk_constrained_limit_up` | 涨停主线风控分支 | stage=data-blocked | decision=blocked | 假设：在不破坏涨停回踩再启动这个主线定义的前提下，更严格的止损、市场过滤或持仓约束可以显著降低回撤。
- `tighter_entry_limit_up` | 涨停主线收紧入场分支 | stage=data-blocked | decision=blocked | 假设：把入选阈值收紧，只保留更接近再次启动位置的个股，可以减少过早买入带来的假突破和大回撤。

## 4. Rejected / Killed 策略
- `legacy_single_branch` | 旧单分支兼容路径 | 原因：它不再代表独立的策略研究问题，只保留历史兼容意义。

## 5. Promoted 策略
- 当前为空

## 6. 当前研究总判断
- 当前研究主线: baseline_limit_up（涨停主线基线分支）
- 当前支线策略: risk_constrained_limit_up（涨停主线风控分支）, tighter_entry_limit_up（涨停主线收紧入场分支）
- 当前最硬 blocker: 默认项目 2026Q1_limit_up 仍缺可用日频 bars，当前不能做新的策略验证。
- 当前轮次类型: 基础设施恢复轮
- 研究策略本身的工作: 本轮未进行实质策略研究，原因是 默认项目 2026Q1_limit_up 仍缺可用日频 bars，当前不能做新的策略验证。；当前先恢复研究前提并保持策略对象可见。
- 恢复基础设施的工作: 本轮主要推进研究前提恢复、长期记忆写回和研究对象显式化。

## 相关 tracked memory
- strategy_board: C:\Users\asus\Documents\Projects\BackTest\memory\projects\2026Q1_limit_up\STRATEGY_BOARD.md
- strategy_candidates_dir: C:\Users\asus\Documents\Projects\BackTest\memory\projects\2026Q1_limit_up\STRATEGY_CANDIDATES
- research_progress: C:\Users\asus\Documents\Projects\BackTest\memory\projects\2026Q1_limit_up\RESEARCH_PROGRESS.md
