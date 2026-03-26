from __future__ import annotations


ROOT_AGENTS_TEMPLATE = """# Research OS Instructions

## Goal
- This repository is Phase 1 of a China A-share research operating system.
- Scope is A-share daily/weekly research only.
- It is not a live trading system and does not promise profitability.

## Response Contract
- Follow `docs/RESPONSE_CONTRACT.md`.
- Default to `CHECKPOINT` replies unless the user explicitly asks for targeted evidence or full forensics.
- `CHECKPOINT` replies must stay strategy-centered and use `Done`, `Evidence`, `Research progress`, `Strategy actions this run`, `Next recommendation`, and `Subagent status`.

## Memory Layers
- Git-tracked long-term memory lives under `memory/projects/<project>/`.
- Runtime/high-noise artifacts live under `data/projects/<project>/meta/` and `artifacts/projects/<project>/`.
- Do not write durable memory only into ignored runtime directories.

## Non-Negotiables
- Never fabricate backtest, validation, or agent results.
- Never delete failed experiments to make the ledger look cleaner.
- Never bypass leakage, tradability, or promotion checks for convenience.
- Never install or invoke new tools silently; log the reason first.

## Required Verification
- Run contract tests for strategy specs, weekday rebalance, tracked memory writeback, and leakage guards.
- Run contract tests for the strategy snapshot, tracked-memory writeback, and the checkpoint format when the reply contract changes.
- Run `python -m quant_mvp research_audit --project <project>`.
- Run `python -m quant_mvp data_validate --project <project>` when data changes.
- Run `python -m quant_mvp agent_cycle --project <project> --dry-run` before trusting the control plane.

## Memory Writeback Contract
- Major repo-level decisions update `docs/DECISION_LOG.md`.
- Durable project summaries update `memory/projects/<project>/PROJECT_STATE.md`.
- Every failed or blocked experiment appends `memory/projects/<project>/POSTMORTEMS.md`.
- Every compact experiment record appends `memory/projects/<project>/EXPERIMENT_LEDGER.jsonl`.
- Every hypothesis refresh updates `memory/projects/<project>/HYPOTHESIS_QUEUE.md`.
- Session handoff artifacts live beside tracked project memory.

## Uncertainty Handling
- Prefer the most conservative, most auditable assumption.
- Write assumptions and unknowns into tracked project memory instead of leaving them only in context.
- If a tool or dependency is missing, stop at the interface boundary, record it, and keep the system reproducible.
"""


QUANT_AGENTS_TEMPLATE = """# quant_mvp Scope

- Core modules must stay deterministic, testable, and auditable.
- Strategy logic belongs in library modules, not scripts.
- Default values must come from schema modules, not ad-hoc literals.
- Memory APIs must preserve the tracked-memory / runtime-artifact split.
"""


SCRIPTS_AGENTS_TEMPLATE = """# scripts Scope

- Scripts orchestrate library code only.
- Do not embed strategy defaults or duplicate selection logic here.
- Durable memory writes must go through the memory writeback layer, not ad-hoc file writes.
"""


TESTS_AGENTS_TEMPLATE = """# tests Scope

- Prefer contract tests over broad smoke tests.
- Cover strategy spec consistency, leakage guards, reproducibility, tracked-memory writeback, and append-only behaviour.
- Tests must clean up tracked-memory side effects for temporary projects.
"""


DOCS_AGENTS_TEMPLATE = """# docs Scope

- Documentation must match the current code, config schema, and audit outputs.
- When behaviour changes, update response contract, strategy specs, decision logs, failure modes, and blueprint docs together.
- Do not retain historical performance claims that cannot be reproduced from the current repo state.
"""


PROJECT_STATE_TEMPLATE = """# 项目状态

- 当前总任务: 保持 Phase 1 Research OS 可复现、可审计，并让 tracked memory 稳定。
- 当前阶段: Phase 1 Research OS
- 当前 blocker: 默认项目在 frozen universe 上仍缺少可用的 validated bars。
- 当前真实能力边界: 工程护栏可用，但真实 default project 研究仍被数据覆盖率阻塞。
- 下一优先动作: 恢复 frozen default universe 可用的 validated bar 快照。
- 最近已验证能力: 仓库虚拟环境中的 contract 与 dry-run orchestration 测试已通过。
- 最近失败能力: 默认项目的 promotion 仍被缺失研究输入阻塞。
"""


HYPOTHESIS_QUEUE_TEMPLATE = """# 假设队列

1. [阻塞] 先恢复 frozen default universe 的 validated daily bars，再重跑 promotion。
2. [待处理] 仅在已验证数据上重新校验审计后的 limit-up screening 规格。
3. [待处理] 任何 promotion 结论前，先与基线和成本压力场景做对比。
"""


EXECUTION_QUEUE_TEMPLATE = """# 执行队列

| 任务ID | 标题 | 影响 | 风险 | 前置条件 | 当前状态 | Owner | 成功条件 | 停止条件 |
|---|---|---|---|---|---|---|---|---|
| recover_daily_bars | 恢复默认项目可用日频 bars | 高 | 低 | 无 | 就绪 | main | `data_validate` 后 blocker 缩小或 `data_ready=True` | full refresh 后仍无新证据且 blocker 未缩小 |
| refresh_research_audit | 刷新 repo truth 与审计基线 | 中 | 低 | 以当前 blocker 重新确认 repo truth | 待排队 | main | 审计结果让下一轮选择更确定 | 审计结果没有带来新的边界信息 |
| refresh_promotion_boundary | 刷新晋级边界诊断 | 高 | 中 | 默认项目具备可研究输入 | 阻塞 | main | promotion 失败边界被重新确认 | 输入仍不足，继续执行 ROI 过低 |
| dry_run_agent_cycle | 跑一次 dry-run control plane | 中 | 中 | 默认项目具备可研究输入 | 阻塞 | main | dry-run 结果带来新的候选或 blocker 收敛 | dry-run 只重复旧 blocker 且没有新信息 |
"""


POSTMORTEMS_TEMPLATE = """# 失败复盘

当前尚无关键失败。后续仅追加高信号失败，记录根因、纠偏动作和当前状态。
"""


RESEARCH_MEMORY_TEMPLATE = """# 研究记忆

## 长期事实
- standalone script 与 modular steps 现已共享同一个经过审计的研究核心。
- tracked long-term memory 位于 `memory/projects/<project>/`，runtime artifacts 位于 `data/` 和 `artifacts/`。

## 负面记忆
- 在 frozen universe 拥有 validated bars 之前，不要信任 default project 的 promotion 结论。
- 被忽略的 runtime 目录不能作为 durable project memory 的唯一存储。

## 下一步记忆
- 在相信任何研究结论之前，先恢复 default project 的 validated bars。
- 保持紧凑的 tracked ledger 与 handoff 文件和 runtime experiment payloads 同步。
"""


VERIFY_LAST_TEMPLATE = """# 最近验证快照

- head: unknown
- branch: unknown
- 通过命令:
  - 未记录
- 失败命令:
  - 未记录
- 默认项目数据状态: unknown
- 工程边界结论: unknown
- 研究边界结论: unknown
"""
