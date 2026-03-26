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
