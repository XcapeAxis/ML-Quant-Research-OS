# Superagent Architecture Redesign

## Goal

Redesign the current Phase 1 Research OS so it can evolve toward an autonomous quant-research superagent that can:

- run multi-direction opportunity and factor search
- iterate and reflect on its own experiments
- discover missing tools, validate them, and use them safely
- coordinate subagents as real workers rather than as governance-only records
- push strategy research toward profitability without pretending the current repo already proves it

This document is a target-architecture proposal, not a claim that the current repo already has these capabilities.

## Current Structural Problems

### 1. The system center is still memory and governance, not research search.

- Evidence:
  - `docs/SYSTEM_BLUEPRINT.md` places strong emphasis on memory retention, readiness, gates, and subagent governance.
  - `quant_mvp/memory/writeback.py` is a large state-derivation hub, while the actual research loop remains thin.
  - `quant_mvp/agent/memory.py` loads almost all tracked files into one context blob instead of retrieving targeted knowledge by task.
- Why this matters:
  - The repo is strong at preserving state, but weak at exploring and comparing many research directions.
  - A superagent cannot be built by adding more memory layers around a narrow search loop.

### 2. The control plane is linear and single-branch.

- Evidence:
  - `quant_mvp/agent/runner.py` takes `hypotheses[0]`, builds one plan, executes one run, and evaluates one result.
  - There is no mission budget, no branch scoring, no portfolio of active experiments, and no branch retirement policy.
  - `quant_mvp/agent/planner.py` only wraps a backend payload into one `ExperimentPlan`.
- Why this matters:
  - Your target needs multiple concurrent research branches, not one hypothesis at a time.
  - Without a branch portfolio, the agent cannot search broadly and then narrow intelligently.

### 3. The tool layer is only an allowlist, not a capability system.

- Evidence:
  - `quant_mvp/agent/tool_registry.py` only loads static lists.
  - `quant_mvp/agent/executor.py` only knows a tiny fixed set of steps and skips everything else.
  - There is no tool discovery, tool sandbox validation, tool capability ledger, or tool retirement flow.
- Why this matters:
  - A superagent that cannot discover, validate, and adopt new tools will stall at the boundary of the initial hand-written tool list.

### 4. The research kernel has no real search space model.

- Evidence:
  - `quant_mvp/factors.py` only supports six hard-coded factors.
  - `quant_mvp/experiment_graph.py` is a good start, but `FactorSpec`, `OpportunitySpec`, and `ToolSpec` are still passive record objects rather than active search-space objects.
  - `quant_mvp/promotion.py` evaluates one current candidate instead of managing a population of candidates.
- Why this matters:
  - Multi-direction opportunity mining and factor discovery require first-class candidate objects, budgets, rankings, and retirement rules.
  - Right now the repo records experiments better than it generates and manages them.

### 5. The validation stack is too shallow for autonomous research.

- Evidence:
  - `quant_mvp/validation/walk_forward.py` treats a window as surviving if it is merely non-empty.
  - `quant_mvp/validation/robustness.py` builds parameter variants but does not actually evaluate their outcomes.
  - `quant_mvp/validation/baselines.py` only returns total-return comparisons and can degrade to `benchmark_available=False`.
  - `quant_mvp/data/validation.py` currently sets `validated_table = clean_table`, so "validated" is not a truly separate evidence layer.
- Why this matters:
  - A superagent needs strong evaluation to avoid self-deception.
  - Weak validation will make an autonomous system optimize toward noisy gates instead of robust edge.

### 6. Subagents exist as governance records, not as a real worker mesh.

- Evidence:
  - `quant_mvp/agent/subagent_controller.py` plans, stores, blocks, merges, and retires subagents, but it does not dispatch real research work units through a shared experiment graph.
  - `quant_mvp/experiment_graph.py` can record `SubagentTask`, but active task execution is not yet wired to experiment outcomes.
- Why this matters:
  - Your target explicitly requires adaptive subagents for parallel exploration depth.
  - Right now subagents are mostly lifecycle bookkeeping.

### 7. The system is still strategy-endpoint-centric.

- Evidence:
  - `quant_mvp/strategy_diagnostics.py` and `quant_mvp/promotion.py` focus on the final gate of one strategy run.
  - `artifacts/projects/2026Q1_limit_up/STRATEGY_FAILURE_REPORT.md` is useful, but it is still a single-strategy blocker report, not a multi-candidate research cockpit.
- Why this matters:
  - A superagent needs a search engine first and a promotion gate second.
  - The current architecture is better at saying "this one failed" than at finding what should replace it.
  - If the long-term target is factor mining plus controllable ML, then single-strategy branches should become control harnesses rather than the architectural center.

## Target Architecture

### Layer 1: Mission Orchestrator

Owns the top-level research mission, budget, target market, time horizon, current constraints, and stopping rules.

- Main objects:
  - `ResearchMission`
  - `MissionBudget`
  - `MissionConstraint`
  - `MissionCheckpoint`

### Layer 2: Research Portfolio Manager

Manages many candidate branches at once instead of one hypothesis at a time.

- Main objects:
  - `ResearchBranch`
  - `BranchPriority`
  - `BranchBudget`
  - `ChampionCandidate`
  - `ChallengerCandidate`

### Layer 3: Research Object Graph

Represents the searchable space as first-class objects.

- Main objects:
  - `DatasetSnapshot`
  - `UniverseSnapshot`
  - `MarketStateSnapshot`
  - `OpportunityCandidate`
  - `FactorCandidate`
  - `FeatureView`
  - `LabelSpec`
  - `ModelCandidate`
  - `StrategyCandidate`
  - `Experiment`
  - `EvaluationRecord`

### Layer 4: Worker Mesh

Turns subagents into real workers tied to branch tasks and experiment states.

- Main worker roles:
  - `ScoutWorker`
  - `ImplementerWorker`
  - `VerifierWorker`
  - `ToolWorker`
  - `ContextWorker`

### Layer 5: Tool Capability Layer

Tracks what tools exist, what is missing, what was attempted, and what is safe to use.

- Main objects:
  - `ToolRequirement`
  - `ToolCandidate`
  - `ToolValidationRun`
  - `ToolCapability`
  - `ToolRetirementRecord`

### Layer 6: Evaluation And Selection Layer

Runs reusable evidence pipelines and updates candidate status.

- Main objects:
  - `ReadinessCheck`
  - `LeakageCheck`
  - `ExecutionQualityCheck`
  - `RobustnessCheck`
  - `EconomicRationaleCheck`
  - `SelectionDecision`

### Layer 7: Knowledge And Memory Layer

Stores structured positive and negative research knowledge instead of only narrative context.

- Main objects:
  - `FailurePattern`
  - `ReusableInsight`
  - `BranchSummary`
  - `DecisionRecord`
  - `EvidenceRecord`

### Layer 8: Governance And Interface Layer

Applies guardrails without becoming the center of the system.

- Main responsibilities:
  - promotion safety
  - memory writeback
  - response contract
  - subagent policy
  - shadow interface boundary

## Required State Machines

### Mission state

`proposed -> scoped -> budgeted -> active -> paused -> closed`

### Branch state

`proposed -> selected -> active -> evidence_pending -> promoted_to_challenger -> promoted_to_champion / rejected / archived`

### Candidate state

`draft -> runnable -> executed -> evaluated -> reusable / weak / invalid / retired`

### Tool state

`missing -> requested -> discovered -> sandbox_validated -> approved -> active -> retired`

### Worker task state

`queued -> assigned -> running -> verified -> merged / canceled / archived`

## What To Keep

- Keep the idea of a research-readiness gate from `quant_mvp/research_readiness.py`.
- Keep leakage auditing as a non-negotiable control from `quant_mvp/validation/leakage.py`.
- Keep project-level experiment records from `quant_mvp/experiment_graph.py` as the seed of the future research object graph.
- Keep tracked memory and writeback from `quant_mvp/memory/writeback.py`, but demote it from system center to support layer.
- Keep strategy failure reports from `quant_mvp/strategy_diagnostics.py`, but treat them as one diagnostic output among many.

## What To Demote Or Replace

- Demote `quant_mvp/agent/runner.py` from "future superagent loop" to "current single-branch control-plane adapter".
- Replace the current step allowlist in `quant_mvp/agent/tool_registry.py` with a real tool capability ledger and validation workflow.
- Replace the six-factor hard-coded factory in `quant_mvp/factors.py` with a searchable factor generation and scoring system.
- Replace shallow evaluation helpers in `quant_mvp/validation/baselines.py`, `walk_forward.py`, and `robustness.py` with stronger reusable evidence pipelines.
- Demote subagent lifecycle bookkeeping to a support role until workers are tied to real experiment tasks and outputs.

## Additional Hidden Risks

- `validated_table = clean_table` in `quant_mvp/data/validation.py` blurs the line between cleaned data and validated evidence.
- The current system does not model market regimes, sector context, event context, or opportunity families as first-class data.
- `load_memory_context()` can keep growing the prompt surface and eventually turn memory into noise.
- The current benchmark path is fragile enough that a missing benchmark can silently weaken decision quality.
- The repo still has one dominant strategy family, so architecture discussions can drift into overfitting that one family instead of designing a true search engine.

## First Implementation Order

1. Build `ResearchMission`, `ResearchBranch`, and a branch budget model.
2. Turn the experiment graph into a real research object graph for factors, opportunities, strategies, and evaluations.
3. Rewire subagents as worker tasks attached to branch and experiment states.
4. Build a tool capability ledger with discovery, sandbox validation, approval, and retirement.
5. Replace weak validation helpers with stronger portfolio-grade evidence pipelines.
6. Only after that, expand search breadth and autonomy aggressively.

## Decision Boundary

The next architecture slice should not be "more memory" and should not be "more governance".

The next slice should be:

- `Mission Orchestrator + Research Portfolio Manager + Research Object Graph`

That is the smallest slice that changes the system center from "recording and gating" to "searching and learning".
