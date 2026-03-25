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
- Change the AKShare daily-bar provider to prefer the Tencent history path and fall back to Eastmoney, because the Eastmoney path is blocked by system-proxy behaviour in the current environment and was leaving the default project at zero coverage.
- Add a policy-driven subagent governance layer with `OFF / AUTO / FORCE` gate, lifecycle tracking, tracked registry/ledger, and runtime payload isolation under `artifacts/projects/<project>/subagents/`.
