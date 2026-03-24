# System Blueprint

## Objective
Build a Phase 1 Research OS for A-share daily/weekly experiments where reliability, reproducibility, and memory retention matter more than headline return.

## Layers
1. Reliable research core
   - schema-driven strategy defaults
   - frozen project paths and manifests
   - audited rank + backtest implementation
2. Data quality layer
   - provider abstraction
   - raw -> cleaned -> validated flow
   - project-scoped quality reports
3. Validation gate
   - leakage checks
   - baselines, walk-forward, cost sensitivity, robustness
   - promotion gate with explicit reasons
4. Memory layer
   - AGENTS files
   - append-only experiment ledger
   - project state, hypothesis queue, postmortems
5. Agent control plane
   - hypothesis -> plan -> execution -> evaluation -> reflection
   - dry-run capable by default
   - tool allowlist enforcement

## Boundaries
- Do not promise profitability.
- Do not treat the agent loop as an override for research gates.
- Do not let scripts own strategy logic.
