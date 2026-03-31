# 研究记忆

## 长期事实
- F1 remains the current mainline and F2.1 remains a bounded challenger under the shared shell.
- The latest F2.1 verifier decision is keep_f2_challenger.
- An export-first Excel console now lives under `artifacts/projects/<project>/excel/` and reads only tracked truth sources.
- The local web monitoring surfaces are frozen until the Excel console covers the core internal scenarios and the user approves deletion.
- On this machine Excel COM is available but VBProject access is blocked, so the console currently uses launcher links instead of embedded VBA macros.
- The Excel console Control sheet now acts as a single-screen dashboard instead of a multi-purpose dump sheet.
- 历史项目名 2026Q1_limit_up 仅作为 legacy alias / 迁移记录保留，不再代表当前活跃项目。

## 仍成立的策略假设
- `f1_elasticnet_v1`: ????????? 5 ????????????????????????
- `f2_structured_latent_factor_v1`: ?? overlay ???????????? F1 ????? latent factor ?????????? challenger?
- `baseline_limit_up`: ?? hand-crafted limit-up ????????????? F1 ?? challenger ???????
- `risk_constrained_limit_up`: ??????????????????????????????
- `tighter_entry_limit_up`: ????????????????????? factor-first ???

## 已被削弱或否定的策略假设
- `r1_predictive_error_overlay_v1`: Drawdown improved materially but annualized return delta was -21.68% and Calmar worsened, so v1 was rejected.
- `legacy_single_branch`: Remains rejected as a historical compatibility path only.

## 负面记忆
- Do not treat F2.1 verifier output as profitability proof or promotion evidence.
- Do not let F2.1 displace F1 mainline until the bounded verifier result is explicitly accepted.
- Do not delete `apps/web` or `dashboard/app.py` before the Excel console is accepted by the user.
- Do not let Excel or launcher scripts become a second source of truth；Python and tracked memory remain canonical.
- Do not overload the Control sheet with secondary ledgers, path dumps, or tiny low-signal charts；those belong on secondary tabs.

## 下一步记忆
- Review the focused Excel Control sheet；if accepted, retire the frozen web UI and continue one more bounded F2.1 variant.
- Review the focused Excel Control sheet and decide whether the frozen web UI can be retired.
- If the Excel console is accepted, delete `apps/web` and `dashboard/app.py` next.
- Keep F1 as the current mainline while F2.1 remains only a bounded challenger.
- Run one more bounded F2.1 variant before widening the model search.

## 策略快照
- 当前规范项目ID: as_share_research_v1
- 历史别名: 2026Q1_limit_up
- 当前研究阶段: 晋级受阻
- 当前轮次类型: 策略推进轮
- 当前主线策略: f1_elasticnet_v1（F1 ElasticNet ????）
- 当前支线策略: f2_structured_latent_factor_v1（F2.1 Structured Latent Deep Factor）, baseline_limit_up（????????）, risk_constrained_limit_up（????????）
- 当前 blocked 策略: risk_constrained_limit_up（????????）, tighter_entry_limit_up（??????????）
- 当前 rejected 策略: r1_predictive_error_overlay_v1（R1.1 Predictive Error Overlay）, legacy_single_branch（????????）
- 当前 promoted 策略: 当前为空
- 系统推进判断: 本轮主要把当前研究结论、阻塞原因和后续验证顺序写清楚，没有新增宽泛系统扩张。
- 策略推进判断: 本轮围绕 f1_elasticnet_v1（F1 ElasticNet ????） 继续收敛研究阻塞；当前最硬的限制仍是 F2.1 shared-shell Top6 max_drawdown 33.58% remains above 30.00%.。
- 规范叙事结论: 规范项目当前处于晋级受阻阶段，真实主阻塞是 F2.1 shared-shell Top6 max_drawdown 33.58% remains above 30.00%.；旧的“缺 bars”叙事已转为历史路径。

## 研究进度
- Data inputs: 起步，1/4。证据：默认项目数据状态：latest core pool `core-0536a20f13d1` stayed consistent through F2 verifier and Excel export.；未发现足够证据支持更高评分。
- Strategy integrity: 部分可用，2/4。证据：单一研究核心与契约护栏已存在；最近已验证能力：Excel console Control sheet now emphasizes mainline, blocker, next action, safe actions, and one large mainline-vs-challenger preview without changing Python as the source of truth.。
- Validation stack: 部分可用，2/4。证据：审计/泄漏/晋级框架存在；最近已验证能力：Excel console Control sheet now emphasizes mainline, blocker, next action, safe actions, and one large mainline-vs-challenger preview without changing Python as the source of truth.。
- Promotion readiness: 阻塞，1/4。证据：当前 blocker：F2.1 shared-shell Top6 max_drawdown 33.58% remains above 30.00%.；研究输入仍不足以支撑晋级评估。
- Subagent effectiveness: 部分可用，2/4。证据：subagent 开关与收尾规则已可用，但本轮配置 gate=OFF、实际执行 gate=OFF；自动收尾 0 个。
- 总体轨迹: 阻塞
- 本轮增量: 无实质变化
- 当前 blocker: F2.1 shared-shell Top6 max_drawdown 33.58% remains above 30.00%.
- 下一里程碑: Review the focused Excel Control sheet；if accepted, retire the frozen web UI and continue one more bounded F2.1 variant.
- 置信度: 中
