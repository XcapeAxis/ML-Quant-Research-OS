# quant_mvp Scope

- Core modules must stay deterministic, testable, and auditable.
- Strategy logic belongs in library modules, not scripts.
- Default values must come from schema modules, not ad-hoc literals.
- New code must keep leakage checks and memory writeback reachable from the CLI.
- Tracked memory belongs under `memory/projects/<project>/`; runtime payloads stay under `data/` and `artifacts/`.
