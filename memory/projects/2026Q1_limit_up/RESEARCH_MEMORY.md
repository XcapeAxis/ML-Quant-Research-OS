# Research Memory

## Durable Facts
- The audited strategy core is now shared by `scripts/run_limit_up_screening.py` and the modular step pipeline.
- Tuesday rebalance is contract-tested after fixing the historical Wednesday drift in the old helper.
- Schema defaults are centralized at a 250-day limit-up window.

## Negative Memory
- The default project currently fails promotion because the local DB has no usable bars for the frozen universe.
- Historical headline returns from old repo states are not considered trustworthy until regenerated from current data.

## Next-Step Memory
- Restore or ingest a validated bar snapshot before trusting any research conclusion on the default project.
- Keep using dry-run agent cycles only as orchestration tests until the data layer is restored.
