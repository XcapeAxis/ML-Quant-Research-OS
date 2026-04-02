# North Star Roadmap

## North Star
- Build an autonomous quant-research superagent that can research, iterate, reflect, discover missing tools, use tools, mine factors and opportunities, and adaptively coordinate subagents.
- Prioritize a factor-first and controllable-ML-first research core instead of treating a single hand-crafted strategy family as the long-term center.
- Do not position the repo as a generic visual factor/ML workflow platform; position it as a visual autonomous research operating system above execution backends and external Flow Engines.
- Keep near-term implementation scoped to China A-share daily and weekly research.
- Reserve clean seams for future multi-market and multi-frequency expansion.
- Keep live trading out of scope; only plan for isolated shadow and paper interfaces.

## Current Reality
- The current repo is a guarded Phase 1 Research OS focused on reproducibility, memory retention, data quality, research readiness, promotion safety, and subagent governance primitives.
- Stage 0A is complete on the default project: the universe was honestly shrunk from 3063 symbols to a research-ready 715-symbol range, and later conclusions must be interpreted only within that refrozen scope.
- The repo is now in Stage 0B: project-level experiment records and a shared strategy failure report exist, but the current agent loop is still far from a real autonomous research loop.
- Profitability is not established and cannot be inferred from pipeline completeness, memory coverage, or a single strategy path on the current 715-symbol universe.

## Dual-Track Strategy
- Track 1: keep Phase 1 Research OS acceptance honest around readiness, auditability, reproducibility, and guarded promotion.
- Track 2: build the superagent incrementally, but treat later-stage autonomy as roadmap work until earlier gates pass.
- Product-layer interpretation: do not compete head-on with mature generic workflow builders; instead own the higher layer of mission orchestration, experiment lineage, reflection, failure analysis, and adapter-based execution through `BackendAdapter` plus `FlowBridgeAdapter`.
- Keep hand-crafted strategy branches as control paths and smoke tests, not as the final product shape; the main alpha roadmap should move toward factors, searchable signals, and controllable ML.
- Do not mix the success criteria: a stronger roadmap does not mean current capability exists, and pilot research results do not prove the north-star end state.
- Profitability claims are staged: first honest readiness plus baseline outperformance, then cross-window and cost robustness, then shadow and paper stability.
- Use tracked memory under `memory/projects/<project>/` plus this roadmap as the only durable macro-goal store; do not create a second parallel memory system.

## Stage Ladder
- Stage 0A: Research readiness. Exit only when the default project clears honest readiness on the frozen universe, so any later promotion failure can be interpreted as strategy quality rather than data incompleteness.
- Stage 0B: Minimal experiment graph. Make `DatasetSnapshot`, `UniverseSnapshot`, `Experiment`, `FactorSpec`, `OpportunitySpec`, `ToolSpec`, `SubagentTask`, and `EvaluationRecord` first-class objects so experiments can be compared structurally rather than through narrative memory alone.
- Stage 1A: Real tool loop. Add guarded `propose -> execute -> evaluate -> retire` experimentation using existing approved tools.
- Stage 1B: High-autonomy tool expansion. Allow sandboxed low-risk tool acquisition only with logged intent, installation reason, regression checks, failure rollback, and a capability ledger; never install silently.
- Stage 2A: Factor and opportunity search. Expand from a fixed factor list to a budgeted searchable space that can generate, rank, prune, and retire candidates.
- Stage 2B: Champion and challenger research loop. Preserve winning experiments, retire weak ones, and carry both success and failure memory forward in structured form.
- Stage 3A: Adaptive subagents. Upgrade subagents from governance bookkeeping to real scout, implementer, and verifier execution with controlled collaboration.
- Stage 3B: Shadow execution interface. Export research candidates to an isolated shadow or paper layer without turning this repo into a live trading system.
- Stage gates are strict: Stage 1 and beyond remain roadmap-only until Stage 0A clears, and each large stage should be split further whenever two independent milestones appear.

## Kill Criteria / Anti-Goals
- Do not claim the repo is already close to a profitable superagent while readiness is still pilot-only.
- Do not treat governance layers, memory writeback, or subagent ledgers as proof of autonomous research depth.
- Do not infer profitability from backtest convenience, a single strategy path, or unverified pilot coverage.
- Do not collapse roadmap stages into one mixed effort that simultaneously claims readiness, autonomy, factor discovery, and profitability.
- Do not bypass leakage, readiness, promotion, or tool-audit controls to make the roadmap look more advanced.

## Interfaces Deferred
- Future command families are reserved, not implemented by this roadmap sync: `experiment_run`, `experiment_compare`, `tool_discover`, `tool_validate`, `factor_search`, `opportunity_search`, `subagent_execute`, and `shadow_cycle`.
- Multi-market and multi-frequency support remain deferred interfaces; near-term implementation stays on A-share daily and weekly research.
- Paper and live execution remain behind a later isolated interface; this repo does not own real order routing or portfolio execution.
- High-autonomy tool discovery remains deferred until automated tests cover discovery, installation, validation, rollback, and ledger writeback end to end.
