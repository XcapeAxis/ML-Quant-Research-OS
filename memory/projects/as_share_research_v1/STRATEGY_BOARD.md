# 策略研究看板

## 1. 主线策略（Primary track）
- `baseline_limit_up` | 涨停主线基线分支 | stage=validation | decision=blocked | 假设：过去一段时间反复出现涨停、随后回到突破起点附近的主板个股，后续更容易再次走强；先把这条主线稳定保存成基线，再评估其它改法。

## 2. 次级策略（Secondary track）
- `risk_constrained_limit_up` | 涨停主线风控分支 | stage=validation | decision=blocked | 假设：在不破坏涨停回踩再启动这个主线定义的前提下，更严格的止损、市场过滤或持仓约束可以显著降低回撤。
- `tighter_entry_limit_up` | 涨停主线收紧入场分支 | stage=validation | decision=blocked | 假设：把入选阈值收紧，只保留更接近再次启动位置的个股，可以减少过早买入带来的假突破和大回撤。

## 3. Blocked 策略
- `baseline_limit_up` | 涨停主线基线分支 | stage=validation | decision=blocked | 假设：过去一段时间反复出现涨停、随后回到突破起点附近的主板个股，后续更容易再次走强；先把这条主线稳定保存成基线，再评估其它改法。
- `risk_constrained_limit_up` | 涨停主线风控分支 | stage=validation | decision=blocked | 假设：在不破坏涨停回踩再启动这个主线定义的前提下，更严格的止损、市场过滤或持仓约束可以显著降低回撤。
- `tighter_entry_limit_up` | 涨停主线收紧入场分支 | stage=validation | decision=blocked | 假设：把入选阈值收紧，只保留更接近再次启动位置的个股，可以减少过早买入带来的假突破和大回撤。

## 4. Rejected / Killed 策略
- `legacy_single_branch` | 旧单分支兼容路径 | 原因：legacy_single_branch 目前只有候选池与实验记录，真正的 verifier 结论仍缺失。

## 5. Promoted 策略
- 当前为空

## 6. 当前研究总判断
- 当前研究主线: baseline_limit_up（涨停主线基线分支）
- 当前支线策略: risk_constrained_limit_up（涨停主线风控分支）, tighter_entry_limit_up（涨停主线收紧入场分支）
- 当前最硬 blocker: 最大回撤 56.50% 高于 30.00%。
- 当前轮次类型: 策略推进轮
- 研究策略本身的工作: 本轮围绕 baseline_limit_up（涨停主线基线分支） 继续收敛研究 blocker；当前最硬的限制仍是 最大回撤 56.50% 高于 30.00%。。
- 恢复基础设施的工作: 本轮主要刷新研究边界、验证状态和长期记忆，而不是继续扩张治理层。

## 相关 tracked memory
- strategy_board: C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\STRATEGY_BOARD.md
- strategy_candidates_dir: C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\STRATEGY_CANDIDATES
- research_progress: C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\RESEARCH_PROGRESS.md
