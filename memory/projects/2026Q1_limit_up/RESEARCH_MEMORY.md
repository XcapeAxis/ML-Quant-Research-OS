# 研究记忆

## 长期事实
- 当前 canonical strategy 仍是 limit_up_screening，主线候选以 baseline_limit_up 作为可追踪基线。
- 历史 branch / evidence ledger 已经留下 baseline_limit_up、risk_constrained_limit_up、tighter_entry_limit_up 与 legacy_single_branch 的真实研究痕迹。
- 本轮新增的是研究可见层，不是新的收益结论。

## 仍成立的策略假设
- `baseline_limit_up`: 过去一段时间反复出现涨停、随后回到突破起点附近的主板个股，后续更容易再次走强；先把这条主线稳定保存成基线，再评估其它改法。
- `risk_constrained_limit_up`: 在不破坏涨停回踩再启动这个主线定义的前提下，更严格的止损、市场过滤或持仓约束可以显著降低回撤。
- `tighter_entry_limit_up`: 把入选阈值收紧，只保留更接近再次启动位置的个股，可以减少过早买入带来的假突破和大回撤。

## 已被削弱或否定的策略假设
- `legacy_single_branch`: 它不再代表独立的策略研究问题，只保留历史兼容意义。

## 负面记忆
- 在 2026Q1_limit_up 恢复可用日频 bars 前，不要把任何策略卡片写成“已验证有效”。
- 不要再用抽象治理语言掩盖当前到底在研究哪条策略。
- legacy_single_branch 只是旧控制面的兼容路径，不应继续占用策略研究主线。

## 下一步记忆
- 先恢复 2026Q1_limit_up 可用日频 bars，再从 baseline_limit_up 开始第一轮 bounded validation。
- 如果 bars 恢复后主线仍卡在回撤，再优先比较 risk_constrained_limit_up 与 baseline_limit_up。
- tighter_entry_limit_up 只在主线 blocker 缩小后再进入对照验证。

## 策略快照
- 当前轮次类型: 基础设施恢复轮
- 当前主线策略: baseline_limit_up（涨停主线基线分支）
- 当前支线策略: risk_constrained_limit_up（涨停主线风控分支）, tighter_entry_limit_up（涨停主线收紧入场分支）
- 当前 blocked 策略: baseline_limit_up（涨停主线基线分支）, risk_constrained_limit_up（涨停主线风控分支）, tighter_entry_limit_up（涨停主线收紧入场分支）
- 当前 rejected 策略: legacy_single_branch（旧单分支兼容路径）
- 当前 promoted 策略: 当前为空
- 系统推进判断: 本轮主要推进研究前提恢复、长期记忆写回和研究对象显式化。
- 策略推进判断: 本轮未进行实质策略研究，原因是 默认项目 2026Q1_limit_up 仍缺可用日频 bars，当前不能做新的策略验证。；当前先恢复研究前提并保持策略对象可见。

## 研究进度
- Data inputs: 起步，1/4。证据：默认项目数据状态：2026Q1_limit_up 尚未写回可直接用于研究的 validated daily bars。；未发现足够证据支持更高评分。
- Strategy integrity: 部分可用，2/4。证据：单一研究核心与契约护栏已存在；最近已验证能力：策略看板、候选卡片、handoff、migration prompt、verify snapshot 与 subagent registry 已接入同一套研究可见层。。
- Validation stack: 部分可用，2/4。证据：审计/泄漏/晋级框架存在；最近已验证能力：策略看板、候选卡片、handoff、migration prompt、verify snapshot 与 subagent registry 已接入同一套研究可见层。。
- Promotion readiness: 阻塞，1/4。证据：当前 blocker：默认项目 2026Q1_limit_up 仍缺可用日频 bars，当前不能做新的策略验证。；研究输入仍不足以支撑晋级评估。
- Subagent effectiveness: 部分可用，2/4。证据：治理与生命周期可用，但本轮保持有效 OFF；gate=AUTO，自动关停 0 个。
- 总体轨迹: 阻塞
- 本轮增量: 无实质变化
- 当前 blocker: 默认项目 2026Q1_limit_up 仍缺可用日频 bars，当前不能做新的策略验证。
- 下一里程碑: 先恢复 2026Q1_limit_up 可用日频 bars，再从 baseline_limit_up 开始第一轮 bounded validation。
- 置信度: 中
