# Research Memory

## Durable Facts
- The default project now has a real daily-bar pilot subset: 150 of 3063 frozen-universe symbols with validated bars.
- The AKShare daily provider now prefers the Tencent history path and falls back to Eastmoney, because the Eastmoney path is blocked by system-proxy behaviour in this environment.
- With real bars present, the promotion gate now executes end-to-end and reports a concrete drawdown failure instead of missing-input failure.

## Negative Memory
- A 150-symbol pilot is not full-universe recovery and does not justify broad research claims.
- The current pilot promotion result is still blocked: max drawdown is 83.38%, far above the 30% Phase 1 limit.
- AUTO subagent gate was re-evaluated on the restored real-input task and still recommended OFF because coordination cost outweighs decomposition value at this stage.

## Next-Step Memory
- Raise validated coverage above the pilot layer before interpreting performance as representative of the frozen universe.
- If drawdown remains extreme after broader coverage, treat it as a strategy problem rather than a data-availability problem.
- Keep tracked memory focused on the pilot/full-recovery boundary so later sessions do not overstate what has been restored.
