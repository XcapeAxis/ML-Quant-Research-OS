# Architecture Redesign Proposal

## Summary
The current repository is an honest and useful Phase 1 Research OS, but it is not yet shaped like an autonomous quant research superagent. The main structural problem is that the governance shell is thicker than the autonomous research kernel. The redesign below recenters the system around research objects, search, tool capability management, and real execution subagents.

## Top 5 Architecture Problems

### 1. Governance Shell Is Thicker Than The Research Kernel
- Severity: critical
- Why it matters:
  - The system is strongest at memory, readiness, and promotion safety, but weak at idea generation, search, and experiment branching.
  - That is the wrong center of gravity for a future autonomous research agent.
- Evidence:
  - [docs/SYSTEM_BLUEPRINT.md] currently dedicates major layers to memory, agent control, and subagent governance, but does not define a first-class research object graph or search plane.
  - [docs/SYSTEM_AUDIT.md] audits reproducibility and readiness well, but does not audit autonomous search depth, tool use quality, or branch management.
  - [docs/NORTH_STAR_ROADMAP.md] is explicit that later-stage autonomy is still roadmap work rather than present architecture.

### 2. The Agent Loop Is Still Linear And Pseudo-Autonomous
- Severity: critical
- Why it matters:
  - A superagent needs to open, compare, retain, and retire multiple branches.
  - The current control plane still behaves like a single-threaded scripted wrapper around audits and promotion.
- Evidence:
  - [quant_mvp/agent/runner.py](C:/Users/asus/Documents/Projects/BackTest/quant_mvp/agent/runner.py) always takes `hypotheses[0]`, builds one linear plan, and returns one experiment path.
  - [quant_mvp/llm/dry_run.py](C:/Users/asus/Documents/Projects/BackTest/quant_mvp/llm/dry_run.py) emits fixed hypotheses and a fixed three-step plan.
  - [quant_mvp/llm/openai_compatible.py](C:/Users/asus/Documents/Projects/BackTest/quant_mvp/llm/openai_compatible.py) returns raw text blobs instead of reliable structured planning and reflection objects.

### 3. Tool Management Is An Allowlist, Not A Capability System
- Severity: high
- Why it matters:
  - Your final goal requires the agent to notice missing tools, justify them, bring them in safely, validate them, and retire them when needed.
  - The current layer does almost none of that.
- Evidence:
  - [quant_mvp/agent/tool_registry.py](C:/Users/asus/Documents/Projects/BackTest/quant_mvp/agent/tool_registry.py) only checks whether a tool name is in `approved_builtin`.
  - [docs/FAILURE_MODES.md] warns against running tools outside the allowlist, but does not define failures for tool acquisition, bad validation, rollback, or stale capability ledgers.
  - [docs/NORTH_STAR_ROADMAP.md] keeps real tool autonomy in a deferred future stage.

### 4. Subagents Exist Mostly As Governance Records, Not Real Workers
- Severity: high
- Why it matters:
  - Your desired end state needs subagents to do real bounded exploration, verification, tool scouting, and experiment execution.
  - The current system mostly plans, records, and retires subagents without making them central to real work execution.
- Evidence:
  - [docs/SYSTEM_BLUEPRINT.md] describes a `Subagent governance layer`, not a real execution layer.
  - [quant_mvp/agent/subagent_controller.py](C:/Users/asus/Documents/Projects/BackTest/quant_mvp/agent/subagent_controller.py) is strong on planning, state transitions, registry sync, and lifecycle logging.
  - [quant_mvp/agent/runner.py](C:/Users/asus/Documents/Projects/BackTest/quant_mvp/agent/runner.py) only records `subagent_tasks` from machine state; it does not delegate actual experiment work to subagents.

### 5. Research Objects Are Still Too Thin And Too Strategy-Specific
- Severity: high
- Why it matters:
  - Multiple-direction opportunity mining and factor mining require a rich object graph, not just one strategy with a few attached fields.
  - The current design still centers one strategy family and a tiny fixed factor surface.
- Evidence:
  - [quant_mvp/experiment_graph.py](C:/Users/asus/Documents/Projects/BackTest/quant_mvp/experiment_graph.py) introduces the right object names, but `FactorSpec` is unused, `OpportunitySpec` is shallow, and the graph still lacks richer objects like `Idea`, `PortfolioCandidate`, `Champion`, `Challenger`, and `ToolCapability`.
  - [quant_mvp/factors.py](C:/Users/asus/Documents/Projects/BackTest/quant_mvp/factors.py) still hardcodes six factors.
  - [quant_mvp/strategy_diagnostics.py](C:/Users/asus/Documents/Projects/BackTest/quant_mvp/strategy_diagnostics.py) and [quant_mvp/promotion.py](C:/Users/asus/Documents/Projects/BackTest/quant_mvp/promotion.py) are tightly tied to the current limit-up strategy path.

## Other Potential Problems
- Memory retrieval is still broad and noisy: [quant_mvp/agent/memory.py](C:/Users/asus/Documents/Projects/BackTest/quant_mvp/agent/memory.py) loads tracked files almost wholesale, which will eventually hurt retrieval quality and context efficiency.
- The current failure taxonomy is too thin for an autonomous research agent. It does not yet cover search-budget runaway, cross-branch interference, false tool confidence, stale benchmark comparisons, or self-confirming reflections.
- There is still no explicit search budget manager, experiment scheduler, or branch portfolio manager.
- Profitability evidence is still mostly strategy-level and not portfolio-level.
- The current next-round plan in [memory/projects/2026Q1_limit_up/NEXT_ROUND_RESEARCH_PLAN.md](C:/Users/asus/Documents/Projects/BackTest/memory/projects/2026Q1_limit_up/NEXT_ROUND_RESEARCH_PLAN.md) is tactically useful, but it still assumes one narrow strategy lane rather than a general research kernel.

## Proposed Top-Level Architecture

### 1. Truth And Snapshot Plane
- versioned universes
- versioned market data and feature snapshots
- benchmark and label snapshots
- reproducible manifest and hashing rules

### 2. Research Object Graph
- `Idea`
- `Hypothesis`
- `FactorSpec`
- `OpportunitySpec`
- `Experiment`
- `Result`
- `Postmortem`
- `ToolCapability`
- `RegimeObservation`
- `PortfolioCandidate`
- `Champion`
- `Challenger`

### 3. Search And Experiment Plane
- experiment generator
- branch scheduler
- search budget manager
- retention and retirement rules
- controlled comparison machinery

### 4. Tool And Capability Plane
- tool adapters
- capability requests
- installation intent logs
- validation suites
- rollback records
- capability ledger

### 5. Evaluation And Profitability Plane
- readiness
- leakage
- tradability
- benchmark comparisons
- walk-forward and robustness
- concentration and portfolio checks
- staged profitability evidence

### 6. Reflection And Memory Plane
- evidence ledger
- decision ledger
- negative memory
- ranked retrieval
- experiment inheritance and branch summaries

### 7. Orchestration And Subagent Plane
- manager / planner
- scout
- tool scout
- experiment builder
- verifier
- reviewer
- memory curator
- bounded work packages and merge rules

### 8. Delivery Boundary
- shadow export
- paper execution interface
- live trading remains outside this repository

## Three Current Design Tendencies To Stop
- Stop adding more governance and documentation layers before the autonomous research kernel becomes first-class.
- Stop treating an allowlist plus a raw LLM wrapper as if that were tool autonomy.
- Stop treating subagents as registry and lifecycle objects unless they are also doing real bounded research work.

## Suggested Migration Order
1. Make the research object graph the real center of the system and add missing objects such as `Idea`, `ToolCapability`, `PortfolioCandidate`, `Champion`, and `Challenger`.
2. Add a real search and experiment plane with branch scheduling, budgets, and retention rules.
3. Replace the current tool allowlist layer with a capability ledger that supports request, validation, rollback, and usage logging.
4. Upgrade subagents from governance-only records into real scout / experiment-builder / verifier workers tied to the search plane.
5. Expand profitability evidence from one strategy path to a candidate portfolio layer, still behind the current Phase 1 safety gates.
