# 研究记忆

## 长期事实
- 长期 north star 仍是一个能够自主研究、迭代、反思、搜索缺失工具、操作工具、挖掘机会与因子，并按需使用 subagents 的量化研究代理。
- Stage 0A 已完成：默认项目已从 3063 个标的收缩到 715 个 data-ready 标的范围；所有更强的研究结论都必须限制在这块恢复后的范围内。
- v1 核心研究池建立在恢复后的 715 标的范围上；在经过 ST、上市历史、近期成交量和流动性过滤后，当前保留 492 个主板标的。
- Architecture Slice 2 已上线：`mission_tick` 会写入 mission、branch、evidence ledger，正式实验 JSON 记录，以及真实的 scout 或 implementer worker-task artifacts。
- `agent_cycle` 只是构建在 `mission_tick` 之上的兼容外壳，不能覆盖主多分支 mission state。
- Subagents 现在是动态资源：系统应按实时任务需要启用、降级、暂停或退役，而不是让它们始终保持 active。
- Worker subagent id 已具备抗碰撞能力，因此并发或相近时间的 run 不会再意外复用同一个 tracked id。
- 旧策略脚本在 legacy project universe 文件存在时仍优先使用它，只有该文件缺失时才回退到新的 core pool；这是刻意保留的兼容桥，而不是最终架构。
- promotion gate 的 baseline 接线此前已修复；本轮又补完了剩余 benchmark 修复，改为独立于 ranked codes 加载配置中的 benchmark 序列。
- 在当前 `as_share_research_v1` run 上，`promote_candidate` 和 `agent_cycle --dry-run` 都已报告 `baselines_status=pass`、`benchmark_available=true`、`equal_weight_available=true`。
- 当前保存的 readiness artifacts 仍将 492 个标的的 core validated snapshot 归类为可进入 promotion-grade checks，因此当前真实 blocker 是 56.50% 的最大回撤，而不是泛化的缺 bars 或 benchmark 完整性问题。
- benchmark 修复后，`equal_weight_total_return` 仍保持 `1.0497515982053982`，说明这次修复没有扩大等权 baseline 的定义。
- 尽管当前 live default-project 名称已经是 `as_share_research_v1`，部分 readiness payload 仍带着历史项目标签 `2026Q1_limit_up`。

## 仍成立的策略假设
- `baseline_limit_up`: 过去一段时间反复出现涨停、随后回到突破起点附近的主板个股，后续更容易再次走强；先把这条主线稳定保存成基线，再评估其它改法。
- `risk_constrained_limit_up`: 在不破坏涨停回踩再启动这个主线定义的前提下，更严格的止损、市场过滤或持仓约束可以显著降低回撤。
- `tighter_entry_limit_up`: 把入选阈值收紧，只保留更接近再次启动位置的个股，可以减少过早买入带来的假突破和大回撤。

## 已被削弱或否定的策略假设
- `legacy_single_branch`: legacy_single_branch 目前只有候选池与实验记录，真正的 verifier 结论仍缺失。

## 负面记忆
- 不要把仍在排队的 verifier 任务描述成已经完成了完整验证。
- 在替换测试完成前，不要把 492 标的的 core research pool 当作所有旧策略路径的直接替代物。
- 不要把策略脚本中当前的兼容性 fallback 当成已经完成的双池迁移。
- 不要因为习惯就让 subagents 长期保持 active；如果某个临时 worker 已经完成，就应暂停或退役它。
- 不要把会写入同一 tracked project state 的顶层命令并行运行，好像它们天然具备并发安全一样。
- 不要基于 Slice 2 宣称工具自治、多方向搜索或盈利性的 superagent 行为；当前 verifier 执行仍不完整，而且策略依然未通过 promotion。
- 除非 `baselines_status` 重新跌破 `pass`，否则不要在 `as_share_research_v1` 上重新打开泛化的 benchmark 缺失诊断；该接线问题已经修复。
- 在当前构建中，不要依赖 `python -m quant_mvp research_readiness` 作为可直接调用的 CLI 步骤；请改用已保存的 readiness artifacts 或受支持的命令。

## 下一步记忆
- 升级 blocker `max_drawdown`: 已停止自动重试，请收窄路径，并在下一次 run 前写回根因诊断。
- 恢复 frozen default universe 可用的 validated bar 快照。
- 先对 `max_drawdown` 做更细的根因诊断，再决定是否进入下一轮 automation iteration。
- 拆解回撤究竟来自时间窗口集中、个股集中，还是持有尾部过长。
- 在 baseline 完整性已经通过后，使用 STRATEGY_FAILURE_REPORT 和 branch ledger 来选择第一条聚焦回撤的 bounded experiment。

## 策略快照
- 当前轮次类型: 策略推进轮
- 当前主线策略: baseline_limit_up（涨停主线基线分支）
- 当前支线策略: risk_constrained_limit_up（涨停主线风控分支）, tighter_entry_limit_up（涨停主线收紧入场分支）
- 当前 blocked 策略: baseline_limit_up（涨停主线基线分支）, risk_constrained_limit_up（涨停主线风控分支）, tighter_entry_limit_up（涨停主线收紧入场分支）
- 当前 rejected 策略: legacy_single_branch（旧单分支兼容路径）
- 当前 promoted 策略: 当前为空
- 系统推进判断: 本轮主要刷新研究边界、验证状态和长期记忆，而不是继续扩张治理层。
- 策略推进判断: 本轮围绕 baseline_limit_up（涨停主线基线分支） 继续收敛研究 blocker；当前最硬的限制仍是 最大回撤 56.50% 高于 30.00%。。

## 研究进度
- Data inputs: 可进入验证，3/4。证据：默认项目数据状态：已就绪覆盖： 715/715 个标的具备已验证 bars (coverage_ratio=1.0000, raw_rows=1441021, cleaned_rows=1419045, validated_rows=1419045).；当前输入已可支撑本阶段验证。
- Strategy integrity: 部分可用，2/4。证据：单一研究核心与契约护栏已存在；最近已验证能力：Tracked memory 已按计划刷新： as_share_research_v1: revalidate spec parity before any new alpha claim。
- Validation stack: 可进入验证，3/4。证据：已记录通过命令 1 条；当前验证栈已可作用于本阶段真实输入。
- Promotion readiness: 当前阶段可运行，4/4。证据：输入与验证均已到位，当前阶段已接近可直接用于晋级决策。
- Subagent effectiveness: 部分可用，2/4。证据：治理与生命周期可用，但本轮保持有效 OFF；gate=AUTO，自动关停 0 个。
- 总体轨迹: 阻塞
- 本轮增量: 无实质变化
- 当前 blocker: 最大回撤 56.50% 高于 30.00%。
- 下一里程碑: 恢复 frozen default universe 可用的 validated bar 快照。
- 置信度: 中
