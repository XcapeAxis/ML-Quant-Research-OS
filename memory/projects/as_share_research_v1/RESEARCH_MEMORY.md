# 研究记忆

## 长期事实
- limit-up screening 路径现在让 standalone script 与 modular steps 共享同一个经过审计的研究核心。
- tracked long-term memory 位于 `memory/projects/<project>/`；runtime artifacts 位于 `data/` 与 `artifacts/`。
- 历史项目名 2026Q1_limit_up 仅作为 legacy alias / 迁移记录保留，不再代表当前活跃项目。
- F1 bounded verifier now compares F1 and baseline_limit_up on the same core universe under one shared TopN shell.
- The latest F1 bounded verifier decision is keep_f1_mainline.
- R1.1 is a bounded predictive-error overlay on top of F1；it only scales exposure and does not update F1 weights.
- The latest R1.1 verifier decision is reject_r1_v1_and_retain_f1_mainline.
- F1 remains the verified mainline after the post-R1.1 frontier reselection.
- R1.2 was selected as the next bounded challenger after R1.1 reduced drawdown but sacrificed too much return.
- F2.1 remains the runner-up challenger for the next model branch.
- Hybrid F1.5 remains deferred until a frozen sidecar contract and offline reproducibility are proven.
- R1.2 is a bounded predictive-error overlay on top of F1；it only scales exposure and does not update F1 weights.
- The latest R1.2 verifier decision is reject_r1_v2_and_promote_f2_next.
- F2.1 is a bounded structured latent deep-factor challenger implemented inside the current scikit-learn stack.
- F2.1 reuses the same core universe, label contract, and monthly retrain rhythm as F1.
- F2.1 writes a latent-factor audit artifact instead of keeping only final scores.
- F2.1 is a bounded structured latent deep-factor challenger built inside the current scikit-learn stack.
- The latest F2.1 verifier decision is keep_f2_challenger.
- An export-first Excel console MVP now lives under `artifacts/projects/<project>/excel/` and reads only tracked truth sources.
- The local web monitoring surfaces are frozen until the Excel console covers the core internal scenarios and the user approves deletion.
- On this machine Excel COM is available but VBProject access is blocked, so the console currently uses launcher links instead of embedded VBA macros.
- The Excel console now exposes dashboard-style strategy metrics, experiment summaries, and embedded preview charts；it is no longer a minimal placeholder workbook.

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
- 在 frozen universe 具备 validated bars 之前，不要信任 default project 的 promotion 结论。
- 被忽略的 runtime 目录不能作为 durable project memory 的唯一存储。
- Do not compare F1 against the old legacy baseline output when the verifier requires the latest core pool only.
- Do not reopen F2/R1 scouting unless the shared-shell verifier says F1 keeps the mainline strongly enough.
- Do not treat R1.1 verifier output as promotion evidence or proof of profitability.
- Do not let R1.1 silently change F1 weights；the v1 overlay only scales exposure.
- Do not treat the R1.1 family as solved just because one overlay reduced drawdown；R1.1 v1 was rejected on return loss.
- Do not jump to F2.1 or Hybrid F1.5 before checking whether a gentler R1.2 overlay can preserve more F1 return.
- Do not let R1.2 update F1 weights；the near-term overlay family must stay exposure-only.
- Do not describe frontier reselection as proof of profitability or promotion readiness.
- Do not treat R1.2 verifier output as promotion evidence or proof of profitability.
- Do not let R1.2 silently change F1 weights；this overlay family must stay exposure-only.
- Do not treat F2.1 prototype metrics as promotion evidence or profitability proof.
- Do not silently replace F1 with F2.1 before the shared-shell verifier completes.
- Do not widen F2.1 into heavy dependencies when the bounded scikit-learn prototype has not been verified yet.
- Do not treat F2.1 verifier output as profitability proof or promotion evidence.
- Do not let F2.1 displace F1 mainline until the bounded verifier result is explicitly accepted.
- Do not delete `apps/web` or `dashboard/app.py` before the Excel console MVP is accepted by the user.
- Do not let Excel or launcher scripts become a second source of truth；Python and tracked memory remain canonical.
- Do not judge the Excel console from the old sparse workbook；the current truth is the dashboard v2 workbook referenced by SESSION_STATE and the latest manifest.

## 下一步记忆
- Use the updated Excel dashboard v2；if it covers the core workflow, retire apps/web and dashboard/app.py next.
- 恢复 frozen default universe 可用的 validated bar 快照。
- Run one more bounded F2.1 variant before widening the model search.
- Reopen LIGHT scouting for Zeno / Popper / Fermat and start F2/R1 frontier scanning.
- Keep F1 as the current mainline while F2.1 remains only a bounded challenger.

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
- 策略推进判断: 本轮围绕 f1_elasticnet_v1（F1 ElasticNet ????） 继续收敛研究阻塞；当前最硬的限制仍是 最大回撤 48.67% 高于 30.00%。。
- 规范叙事结论: 规范项目当前处于晋级受阻阶段，真实主阻塞是 最大回撤 48.67% 高于 30.00%。；旧的“缺 bars”叙事已转为历史路径。

## 研究进度
- Data inputs: 起步，1/4。证据：默认项目数据状态：latest core pool `core-0536a20f13d1` stayed consistent through F2 verifier and Excel export.；未发现足够证据支持更高评分。
- Strategy integrity: 部分可用，2/4。证据：单一研究核心与契约护栏已存在；最近已验证能力：Excel console dashboard v2 exported a valid workbook with denser strategy metrics, experiment summaries, embedded preview charts, and safe launcher actions while keeping Python as the only source of truth.。
- Validation stack: 起步，1/4。证据：仅具备基础验证入口，尚缺少足够已记录证据支持更高评分。
- Promotion readiness: 阻塞，1/4。证据：当前 blocker：最大回撤 48.67% 高于 30.00%。；研究输入仍不足以支撑晋级评估。
- Subagent effectiveness: 部分可用，2/4。证据：subagent 开关与收尾规则已可用，但本轮配置 gate=OFF、实际执行 gate=OFF；自动收尾 0 个。
- 总体轨迹: 阻塞
- 本轮增量: 无实质变化
- 当前 blocker: 最大回撤 48.67% 高于 30.00%。
- 下一里程碑: Use the updated Excel dashboard v2；if it covers the core workflow, retire apps/web and dashboard/app.py next.
- 置信度: 低
