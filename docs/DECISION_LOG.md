# Decision Log

## 2026-03-24
- Keep `quant_mvp/db.py`, `quant_mvp/backtest_engine.py`, `quant_mvp/selection.py`, and `quant_mvp/project.py` as the reusable low-level core because they already expose deterministic, testable primitives.
- Rewrite `scripts/run_limit_up_screening.py` so it cannot drift away from the modular pipeline.
- Introduce schema modules (`quant_mvp/strategy_schema.py`, `quant_mvp/config_schema.py`) as the single source of truth for defaults and contracts.
- Introduce provider/data validation abstractions instead of binding update logic directly to AKShare response quirks.
- Keep the agent control plane dry-run capable by default; a live LLM backend is optional and never required for tests.

## 2026-03-25
- Move durable project memory into git-tracked `memory/projects/<project>/`.
- Keep raw cycle payloads, manifests, and other high-noise outputs under ignored runtime directories.
- Add handoff, migration prompt, verify snapshot, and machine-state files so sessions can migrate without rereading the whole repository.

## 2026-03-26
- Keep benchmark baseline input separate from the strategy close panel so promotion and dry-run evaluation can load `000001` even when it is not ranked, without changing equal-weight baseline semantics.
- Make the explicit benchmark-series path canonical for strategy diagnostics so `benchmark_missing:000001` is treated as a wiring regression, not as proof that the database lacks the benchmark.
- Keep the automation loop bounded and stateful across runs: repeated blockers now upgrade from normal tracking to root-cause guidance on the second sighting and escalated stop-on-writeback on the third.
- Keep repo-local automation execution pinned to the repository virtualenv when available so scheduled runs do not depend on whichever `python` happens to be on PATH.
- Add a tracked Strategy Research Visibility Layer so the system always exposes which strategy candidates are being researched, which are primary / secondary / blocked / rejected / promoted, and why the current run did or did not advance real strategy research.
- Split subagents into strategy-research and infrastructure types in tracked memory; research subagents must bind a `strategy_id`, while infrastructure subagents must say which blocker or prerequisite they are clearing for later research.
- Keep automation CHECKPOINT replies research-centered: `Done / Evidence / Next action / Subagent status`, with explicit Chinese statements when a run is only doing infrastructure recovery rather than substantive strategy work.
- Make `as_share_research_v1` the single canonical active project id; keep `2026Q1_limit_up` only as an explicit legacy alias or archived migration reference.
- Unify the active blocker story around the current truth: default-project data inputs are ready, and the live blocker is promotion-stage max drawdown rather than missing daily bars.
- Add tracked `STRATEGY_ACTION_LOG.jsonl` and `RESEARCH_ACTIVITY.md` so every run states whether real strategy research happened, who did it, what changed, and when the run was infrastructure-only.
- Distinguish configured subagent gate from the effective gate used in the current run, and keep user-facing summaries in direct Chinese research language instead of abstract system-orchestration language.
- Formalize dual universe policy for the active project: `full_a_mainboard_incl_st` is the research baseline and `full_a_mainboard_ex_st` is the deployment control slice.
- Stop filtering ST names out at symbol-freeze time; universe inclusion/exclusion must now happen explicitly at the universe-profile layer.
- Treat current ST impact as unidentifiable on the frozen 715-symbol snapshot because source ST exposure is zero; do not over-interpret identical incl/ex-ST results as proof that ST never matters.
- Keep `baseline_limit_up` as the comparison control, advance `risk_constrained_limit_up` as the next mainline candidate, and defer `tighter_entry_limit_up` until the drawdown decomposition is exhausted.

## 2026-03-27
- Retire the old 715-stock pool from the active research path; keep it only as a legacy archive and migration reference.
- Make `cn_a_mainboard_all_v1` the only canonical active universe for `as_share_research_v1`.
- Rebuild the active universe from exchange security-master metadata instead of patching the old `symbols.csv`.
- Keep `ST` / `*ST` inside the canonical universe as labels only, never as an exclusion filter.
- Fix the coverage-gap policy so a fixed canonical universe cannot auto-shrink or silently refreeze back into a legacy sample.
- Reset strategy truth after the universe change: `baseline_limit_up` becomes the only active baseline rebuild track, while `risk_constrained_limit_up` and `tighter_entry_limit_up` are downgraded to legacy comparison only until the new baseline is rebuilt.
- Recover canonical coverage with missing-only incremental backfill instead of rerunning the whole universe; post-cutoff IPOs are structural no-bars, not provider failures.
- Keep `validation-ready` as the highest automatic stage for this recovery pass even after baseline rerun; `research-ready` requires a later explicit promotion gate and does not unlock legacy branch restoration here.
- Interpret the rebuilt baseline only as `baseline_validation_ready` on the canonical universe until the remaining provider failures are retried and a later promotion review is passed.

## 2026-03-30
- Treat the current canonical blocker as a branch-ranking contract bug, not as a data-recovery or benchmark-missing problem.
- Prioritize syncing tracked memory and memory tests to the current canonical truth before doing more strategy comparison work.
- Prefer repairing the `branch pool -> ranking` contract over temporary parameter hotfixes; the hotfix path may be used only as a bounded diagnostic, not as the main fix.
- Keep `baseline_limit_up` as the control branch even though `risk_constrained_limit_up` can already generate rank output; do not let a working challenger replace a still-broken control branch.
- Keep subagents dynamically gated: default `OFF`, upgrade to `LIGHT` only for low-coupling scouting or cross-checks, and retire temporary subagents immediately after they finish.
- Re-sequence the next round into `P0 -> P1 -> P2`: fix tracked memory writeback truth first, then repair the `baseline_limit_up` branch-pool contract, then rerun bounded verification.
- Retire temporary workers that do not return useful results in time; the main agent remains responsible for the final plan and for deciding when subagents are worth the coordination cost.
- Treat standalone hand-crafted strategy research as a control harness, not as the long-term product center; the main alpha direction should pivot toward factor search plus controllable machine learning.
- After a 2026-03-30 frontier survey, rank the next research stack as: `regularized cross-sectional factor model` first, `structured latent deep factor` second, `supply-chain/similarity event propagation alpha` third, and `graph regime + regime-aware portfolio` as a platform control layer.
- De-prioritize full black-box transformers, RL, LLM direct stock picking, TabPFN-as-core, and direct transcript-to-signal pipelines for the first production research wave.
- Reorder the implementation path to `P0 -> F0 -> F1`, where `F1` is the first factor/ML MVP and the old rule-based branch remains only a control benchmark.
- Extend the post-F1 roadmap from static factor modeling toward dynamic adaptation: add `Deep SSM` candidates under `F2`, `test-time adaptation` and predictive-error regime signals under `R1`, and reserve later `financial world model` / `multi-agent game` stress-testing paths.
- Expand the object contract so future implementations must track `ModelCandidate.is_online_adaptive`, `ModelCandidate.update_frequency`, `RegimeSpec.regime_transition_latency`, and `EvaluationRecord.adversarial_robustness` plus `regime_transition_drawdown`.
- Complete `P0` by tightening blocker classification so non-data issues no longer fall back to the generic “missing validated bars” narrative in tracked memory.
- Replace the old placeholder strategy-board output with a direct view of current branches, blockers, and next-step ordering.
- Treat `as_share_research_v1` as `validation-ready` for current control-plane work; the latest verified strategy blocker is `max_drawdown = 48.67% > 30%`, not missing bars.
- Keep `baseline_limit_up` as a control sample rather than the long-term platform center.
- Make `F0 -> F1` the next implementation path, and keep the Subagent Gate effectively `OFF` during `F0` because the object-layer changes are tightly coupled and not worth splitting yet.
- Complete `F0` by making `FactorCandidate / FeatureView / LabelSpec / ModelCandidate / RegimeSpec / EvaluationRecord` first-class experiment objects and wiring them into real `mission_tick` experiment records.
- Extend `load_memory_context()` with recent structured experiment summaries so future control-plane turns do not rely only on narrative markdown.
- Treat `F0` as an object-layer milestone only; it does not mean `F1` factor modeling has already happened.
- Rebase the next implementation step to `F1`: build the first regularized cross-sectional factor-model MVP while keeping `baseline_limit_up` as the control branch.
- Keep the dynamic subagent rule explicit in durable memory: default `OFF`, escalate only when parallel low-coupling work or independent verification justifies it, and retire temporary subagents immediately after use.
- Land `F1` as a separate factor-model command instead of burying it inside the old rule-based control plane: the first MVP is `technical + liquidity features -> 5-day excess return label -> monthly ElasticNet retrain -> TopN backtest`.
- Keep `F1` prototype-only for now: it writes formal experiment objects and tracked memory, but it does not enter `promote_candidate` and must not be described as profitability proof while top6 max drawdown still sits around `-37.89%`.
## 2026-03-30T12:10:25+00:00 - as_share_research_v1
- Decision: `keep_f1_mainline`
- Reason: the shared-shell bounded verifier says F1 now beats the control branch strongly enough to keep the factor mainline and reopen LIGHT scouting for F2/R1.
- Evidence: `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\f1\F1_BOUNDED_VERIFIER.md`

## 2026-03-31 - as_share_research_v1
- Complete one `LIGHT` frontier-scouting round after the F1 verifier pass instead of jumping directly into F2 or hybrid experimentation.
- Choose `R1.1` as the unique next build target because the current blocker is drawdown reduction, and a constrained regime/risk overlay is the most direct, lowest-cost path to attack it.
- Keep `F2.1` as the runner-up challenger: it remains promising, but it should come after the first bounded R1.1 check rather than before it.
- Defer `Hybrid F1.5` to a future frozen sidecar experiment; do not let foundation-model dependencies or end-to-end adaptation hijack the near-term mainline.
- Keep subagents dynamically gated: this round used `LIGHT` for three low-coupling scouts (`Zeno / Popper / Fermat`), and all three were retired immediately after the decision was made.
## 2026-03-31T06:49:02+00:00 - as_share_research_v1
- Decision: `keep_f1_mainline`
- Reason: the shared-shell bounded verifier says F1 now beats the control branch strongly enough to keep the factor mainline and reopen LIGHT scouting for F2/R1.
- Evidence: `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\f1\F1_BOUNDED_VERIFIER.md`

## 2026-03-31T08:20:00+00:00 - as_share_research_v1
- Decision: select `R1.2` as the next bounded challenger; keep `F2.1` as runner-up; defer `Hybrid F1.5`.
- Reason: `R1.1 v1` proved the overlay family can reduce drawdown, but its return drag was too large. The live blocker is still drawdown control, and `R1.2` is the lowest-cost, most auditable next test before promoting a new model family.
- Evidence:
  - `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\r1\R1_VERIFY_REPORT.md`
  - `C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\FRONTIER_NEXT_STEP_DECISION.md`
## 2026-03-31T08:20:42+00:00 - as_share_research_v1
- Decision: `keep_f1_mainline`
- Reason: the shared-shell bounded verifier says F1 now beats the control branch strongly enough to keep the factor mainline and reopen LIGHT scouting for F2/R1.
- Evidence: `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\f1\F1_BOUNDED_VERIFIER.md`
## 2026-03-31T08:21:34+00:00 - as_share_research_v1
- Decision: `promote_f2_1_next_after_r1_2_reject`
- Reason: R1.2 still reduced too much return, so F2.1 is now the next implementation slot while F1 remains mainline.
- Evidence: `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\r1\r1_predictive_error_overlay_v2\R1_VERIFY_REPORT.md`
## 2026-03-31T08:23:25+00:00 - as_share_research_v1
- Decision: `promote_f2_1_next_after_r1_2_reject`
- Reason: R1.2 still reduced too much return, so F2.1 is now the next implementation slot while F1 remains mainline.
- Evidence: `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\r1\r1_predictive_error_overlay_v2\R1_VERIFY_REPORT.md`
## 2026-03-31T08:29:32+00:00 - as_share_research_v1
- Decision: `promote_f2_1_next_after_r1_2_reject`
- Reason: R1.2 still reduced too much return, so F2.1 is now the next implementation slot while F1 remains mainline.
- Evidence: `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\r1\r1_predictive_error_overlay_v2\R1_VERIFY_REPORT.md`
## 2026-03-31T08:35:19+00:00 - as_share_research_v1
- Decision: `promote_f2_1_next_after_r1_2_reject`
- Reason: R1.2 still reduced too much return, so F2.1 is now the next implementation slot while F1 remains mainline.
- Evidence: `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\r1\r1_predictive_error_overlay_v2\R1_VERIFY_REPORT.md`
## 2026-03-31T08:37:18+00:00 - as_share_research_v1
- Decision: `promote_f2_1_next_after_r1_2_reject`
- Reason: R1.2 still reduced too much return, so F2.1 is now the next implementation slot while F1 remains mainline.
- Evidence: `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\r1\r1_predictive_error_overlay_v2\R1_VERIFY_REPORT.md`
## 2026-03-31T09:15:48+00:00 - as_share_research_v1
- Decision: `keep_f1_mainline`
- Reason: the shared-shell bounded verifier says F1 now beats the control branch strongly enough to keep the factor mainline and reopen LIGHT scouting for F2/R1.
- Evidence: `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\f1\F1_BOUNDED_VERIFIER.md`
## 2026-03-31T10:11:26+00:00 - as_share_research_v1
- Decision: `keep_f1_mainline`
- Reason: the shared-shell bounded verifier says F1 now beats the control branch strongly enough to keep the factor mainline and reopen LIGHT scouting for F2/R1.
- Evidence: `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\f1\F1_BOUNDED_VERIFIER.md`
## 2026-03-31T11:40:00+08:00 - repo
- Decision: freeze the local web UIs and move the internal monitoring path to an export-first Excel console MVP.
- Reason: the repo's current internal monitoring needs are read-heavy, operator-facing, and Windows-local; the local web surfaces add more UI and coordination cost than value for this stage.
- Evidence:
  - `C:\Users\asus\Documents\Projects\BackTest\docs\EXCEL_CONSOLE_MVP.md`
  - `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\excel\feed\manifest.json`
## 2026-03-31T12:21:20+00:00 - as_share_research_v1
- Decision: `keep_f1_mainline`
- Reason: the shared-shell bounded verifier says F1 now beats the control branch strongly enough to keep the factor mainline and reopen LIGHT scouting for F2/R1.
- Evidence: `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\f1\F1_BOUNDED_VERIFIER.md`
## 2026-03-31T12:41:52+00:00 - as_share_research_v1
- Decision: `keep_f1_mainline`
- Reason: the shared-shell bounded verifier says F1 now beats the control branch strongly enough to keep the factor mainline and reopen LIGHT scouting for F2/R1.
- Evidence: `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\f1\F1_BOUNDED_VERIFIER.md`
## 2026-03-31T20:45:00+08:00 - repo
- Decision: keep the Excel console MVP as the active internal UI path with launcher-link fallback, and keep the local web surfaces frozen but undeleted.
- Reason: the workbook now opens successfully in Excel as a real `.xlsm` package after COM `SaveAs(..., 52)` conversion, while this machine still blocks writable `VBProject` access, so embedded VBA remains out of scope for the MVP.
- Evidence:
  - `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\excel\ResearchConsole.xlsm`
  - `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\excel\feed\manifest.json`
  - `C:\Users\asus\Documents\Projects\BackTest\docs\EXCEL_CONSOLE_MVP.md`
## 2026-03-31T23:50:00+08:00 - repo
- Decision: upgrade the Excel console from a sparse MVP sheet pack to a denser dashboard-style console with metric cards, comparison charts, and embedded plot previews, while still keeping the web surfaces frozen and undeleted.
- Reason: the first workbook proved the export-first path was viable, but it was too sparse to serve as a real internal monitoring console; adding denser summaries and visual context materially improves usability without reintroducing a local web stack.
- Evidence:
  - `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\excel\feed\manifest.json`
  - `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\excel\ResearchConsole_20260331T153849Z.xlsm`
  - `C:\Users\asus\Documents\Projects\BackTest\docs\EXCEL_CONSOLE_MVP.md`
## 2026-04-01T00:22:00+08:00 - repo
- Decision: refocus the Excel console `Control` sheet into a single-screen dashboard that emphasizes mainline, blocker, next action, safe actions, and one large mainline-vs-challenger preview.
- Reason: the denser dashboard proved the export-first Excel path worked, but the first control page still mixed primary signals with too many secondary details and small charts. The home sheet now acts as a driving console, while lower-priority ledgers stay on secondary tabs.
- Evidence:
  - `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\excel\ResearchConsole.xlsm`
  - `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\excel\feed\manifest.json`
  - `C:\Users\asus\Documents\Projects\BackTest\docs\EXCEL_CONSOLE_MVP.md`
## 2026-04-01T11:20:00+08:00 - repo
- Decision: rebuild the Excel console into a Chinese-first cockpit that separates “research truth summary” from “home-page control cards” and keeps the home sheet as a single-screen dashboard.
- Reason: the previous dashboard proved the Excel path was viable, but the home sheet still mixed stale research state, low-priority details, and undersized charts. The new contract moves durable summary truth into dedicated feeds, keeps the home page focused on primary signals, and pushes ledgers to secondary tabs.
- Evidence:
  - `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\excel\feed\research_summary.csv`
  - `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\excel\feed\control_cards.csv`
  - `C:\Users\asus\Documents\Projects\BackTest\docs\EXCEL_CONSOLE_MVP.md`
## 2026-04-01T12:10:00+08:00 - repo
- Decision: retire Excel launcher scripts and switch the console to a safe read-only `.xlsx` dashboard with copyable terminal commands.
- Reason: the generated `.cmd` launchers were flagged and removed by local antivirus, so keeping script-based actions would make the console unreliable and unsafe-by-default. The dashboard now stays read-only, preserves Python as the sole execution path, and exposes commands as text instead of executable links.
- Evidence:
  - `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\excel\ResearchConsole.xlsx`
  - `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\excel\feed\manifest.json`
  - `C:\Users\asus\Documents\Projects\BackTest\docs\EXCEL_CONSOLE_MVP.md`
## 2026-04-02T00:00:00+08:00 - repo
- Decision: harden the Excel console into a script-free path and auto-clean legacy executable leftovers during export.
- Reason: antivirus deletion proved that even dormant launcher remnants create operational risk and confusion. The console must now be plain `.xlsx`, command-text only, and self-cleaning with respect to old `.cmd/.bat/.ps1/.vbs/.xlsm` artifacts.
- Evidence:
  - `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\excel\ResearchConsole.xlsx`
  - `C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\excel\feed\manifest.json`
  - `C:\Users\asus\Documents\Projects\BackTest\docs\EXCEL_CONSOLE_MVP.md`
