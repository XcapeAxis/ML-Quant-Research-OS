# Failure Modes

## Research Integrity
- Using standalone entrypoints that diverge from the audited strategy core.
- Letting README claims outlive the artifacts or manifests that once supported them.
- Running selection or backtests without a frozen universe snapshot.

## Data and Leakage
- Treating raw AKShare bars as validated data without cleaning and validation reports.
- Using same-day prices as forward labels instead of next-trading-day returns.
- Ignoring zero-volume, suspension, or limit-lock proxies when ranking or evaluating.

## Agent Control
- Allowing the agent loop to skip memory writeback.
- Letting tools execute outside the allowlist or without being logged.
- Overwriting failure records instead of appending postmortems and experiment ledgers.

## Memory Layering
- Writing durable project memory only into ignored runtime directories.
- Mixing compact tracked ledgers with full raw experiment payloads.
- Starting a new chat without refreshing handoff, migration prompt, and machine-state summaries.
