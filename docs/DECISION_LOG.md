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
- Keep the automation loop bounded and stateful across runs: repeated blockers now upgrade from normal tracking to root-cause guidance on the second sighting and escalated stop-on-writeback on the third.
- Keep repo-local automation execution pinned to the repository virtualenv when available so scheduled runs do not depend on whichever `python` happens to be on PATH.
- Add a tracked Strategy Research Visibility Layer so the system always exposes which strategy candidates are being researched, which are primary / secondary / blocked / rejected / promoted, and why the current run did or did not advance real strategy research.
- Split subagents into strategy-research and infrastructure types in tracked memory; research subagents must bind a `strategy_id`, while infrastructure subagents must say which blocker or prerequisite they are clearing for later research.
- Keep automation CHECKPOINT replies research-centered: `Done / Evidence / Next action / Subagent status`, with explicit Chinese statements when a run is only doing infrastructure recovery rather than substantive strategy work.
