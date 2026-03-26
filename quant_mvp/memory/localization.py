from __future__ import annotations

import re


_EXACT_TEXT = {
    "unknown": "未知",
    "none": "无",
    "none recorded": "未记录",
    "none recorded yet": "尚未记录",
    "n/a": "不适用",
    "not_run": "尚未运行",
    "not_fixed": "未修复",
    "fixed": "已修复",
    "No iterative loop run has been recorded yet.": "尚未记录任何高阶迭代 loop 运行。",
    "No recorded failures yet in this bootstrap state. Append new failures with root cause, corrective action, and current resolution status.": "当前 bootstrap 状态尚无失败复盘。后续仅追加高信号失败，记录根因、纠偏动作和当前状态。",
    "Task breadth is below the minimum threshold for safe decomposition.": "任务广度尚未达到安全拆分的最低阈值。",
    "The work is still narrow enough for one integrating agent.": "当前工作仍足够单线，保持一个整合代理最稳妥。",
    "Subtasks are too coupled to split cleanly.": "子任务耦合度过高，暂不适合干净拆分。",
    "High coupling would turn subagents into coordination overhead.": "高耦合会让 subagents 只剩协调成本。",
    "File overlap is too high for efficient parallel work.": "文件重叠过高，不适合高效并行。",
    "The same hot files would need frequent merges, so splitting is suppressed.": "热点文件重叠严重，若拆分会频繁合并，因此抑制拆分。",
    "The coordination-adjusted score is too low.": "协调收益校正后的分数过低。",
    "Validation and isolation benefits do not yet offset decomposition cost.": "验证与隔离收益暂时还不足以覆盖拆分成本。",
    "Subagent policy files are unavailable.": "subagent policy 文件不可用。",
    "No subagents were activated.": "本轮没有启用额外 subagents。",
    "Gate is explicitly OFF.": "gate 被显式设为 OFF。",
    "Subagent decomposition is disabled for this task.": "当前任务禁用 subagent 拆分。",
    "Independent work packages exist and the coordination-adjusted score justifies controlled decomposition.": "独立工作包已经成立，协调成本校正后仍值得受控拆分。",
    "Promotion gate diagnostics were generated and written to runtime artifacts.": "晋级门诊断已生成并写入 runtime artifacts。",
    "data_validate refreshed cleaned bars, coverage-gap artifacts, and research readiness.": "`data_validate` 已刷新清洗 bars、覆盖缺口产物与 research readiness。",
    "data_validate refreshed readiness artifacts and tracked memory.": "`data_validate` 已刷新 readiness 产物与 tracked memory。",
    "Validated data recovery, coverage-gap analysis, and readiness writeback all executed.": "已执行已验证数据恢复、覆盖缺口分析与 readiness 写回。",
    "Promotion-grade research can proceed on the current validated snapshot.": "当前已验证快照已满足 promotion-grade research 的前置条件。",
    "Coverage improved, but the readiness gate is still blocking broad research claims.": "覆盖率已有改善，但 readiness gate 仍阻止更广泛的研究结论。",
    "The repo truth still points to a data/readiness blocker, so the lowest-risk next action is to refresh validated inputs and readiness.": "当前 repo truth 仍指向数据或 readiness blocker，因此最低风险的下一步是刷新已验证输入和 readiness。",
    "Refresh coverage-gap and readiness artifacts, then rescan the blocker.": "刷新 coverage-gap 与 readiness 产物，然后重新扫描 blocker。",
    "The current blocker is strategy- or gate-specific, so promotion diagnostics give the highest-signal next truth without widening the change set.": "当前 blocker 属于策略或 gate 维度，因此 promotion diagnostics 是不扩大改动面的最高信号下一步。",
    "Refresh the promotion gate and strategy failure report for the current research universe.": "刷新当前研究宇宙的 promotion gate 与策略失败报告。",
    "A control-plane rescan should start by refreshing the repo audit before another dry-run cycle.": "控制面重新扫描前，应先刷新 repo audit，再进入下一次 dry-run。",
    "Refresh audit docs and confirm the current repo boundary.": "刷新 audit 文档，并确认当前 repo 边界。",
    "After the current truth is refreshed, the next low-risk step is one dry-run control-plane cycle.": "当前 truth 刷新后，下一步最低风险动作是一轮控制面的 dry-run cycle。",
    "Regenerate one bounded cycle record plus updated hypothesis and evaluation state.": "重新生成一条 bounded cycle 记录，并更新 hypothesis 与评估状态。",
    "Validated inputs and readiness improved enough to justify one more bounded iteration.": "已验证输入与 readiness 已改善到足以支持再做一轮 bounded iteration。",
    "Task breadth is below the minimum threshold for safe decomposition.": "任务广度尚未达到安全拆分的最低阈值。",
    "No additional unconfirmed questions have been recorded yet.": "当前尚未记录新的未确认问题。",
    "Do not move durable memory back into ignored runtime directories.": "不要把 durable memory 再挪回被忽略的 runtime 目录。",
    "Do not trust default-project research claims until validated bars exist for the frozen universe.": "在 frozen universe 具备已验证 bars 前，不要信任 default project 的研究结论。",
    "Run the tracked-memory and contract test suite first.": "先跑 tracked-memory 与 contract test 套件。",
    "verified_progress": "已验证进展",
    "blocker_clarified": "blocker 已被澄清",
    "no_meaningful_progress": "没有显著进展",
    "direction_corrected": "方向已纠偏",
}

_STOP_REASONS = {
    "no_verified_progress": "本轮没有产生可验证进展。",
    "no_new_information_twice": "连续两轮没有新增信息，自动停止。",
    "no_effective_progress_twice": "连续两轮没有有效进展，自动停止。",
    "low_roi_repeated_blocker": "同一 blocker 已升级且继续推进 ROI 很低，自动停止。",
    "verification_failed_scope_expanded": "验证失败范围扩大，已立即停止。",
    "max_iterations_reached": "已达到最大迭代次数。",
    "target_iterations_reached": "已达到目标迭代次数，继续推进的边际收益下降。",
    "sufficient_campaign_progress": "本轮已完成足够高质量的 campaign 进展。",
    "clarify_only_limit_reached": "澄清型动作已达到上限，自动停止。",
    "stage_stop_condition_met": "已达到当前阶段停止条件。",
    "insufficient_context": "当前上下文不够清晰，继续推进风险过高。",
    "worktree_not_suitable": "当前工作树状态不适合继续自动推进。",
}

_STATUS_TEXT = {
    "pending": "待处理",
    "blocked": "阻塞",
    "active": "进行中",
    "merged": "已合并",
    "retired": "已退休",
    "canceled": "已取消",
    "archived": "已归档",
    "refactored": "已重构",
    "proposed": "已提议",
}


def zh_bool(value: bool) -> str:
    return "是" if bool(value) else "否"


def zh_status(value: str) -> str:
    key = str(value or "").strip().lower()
    return _STATUS_TEXT.get(key, value)


def zh_stop_reason(value: str) -> str:
    key = str(value or "").strip()
    return _STOP_REASONS.get(key, humanize_text(key))


def humanize_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "未记录"
    if text in _EXACT_TEXT:
        return _EXACT_TEXT[text]
    if text in _STOP_REASONS:
        return _STOP_REASONS[text]

    lowered = text.lower()
    if lowered in {"true", "false"}:
        return zh_bool(lowered == "true")

    replacements = {
        "Max drawdown": "最大回撤",
        "exceeds": "高于",
        "Benchmark or equal-weight baselines are incomplete": "基准或等权基线不完整",
        "Promotion gate blocked the current candidate.": "当前候选仍被晋级门阻塞。",
        "Promotion gate blocked on strategy-quality checks.": "晋级门仍被策略质量检查阻塞。",
        "Promotion gate blocked on data readiness.": "晋级门仍被数据就绪度阻塞。",
        "Promotion gate blocked:": "晋级门阻塞：",
        "Resolve the failed gate reasons before the next promotion attempt.": "在下一次 promotion 前，先解决当前 gate 失败原因。",
        "Use the strategy failure report to design the next risk-focused experiment.": "基于策略失败报告设计下一轮以风险为中心的实验。",
        "Use STRATEGY_FAILURE_REPORT to design the next risk-focused experiment.": "基于 STRATEGY_FAILURE_REPORT 设计下一轮以风险为中心的实验。",
        "Use the strategy failure report and the branch ledger to choose the next bounded branch experiment.": "结合策略失败报告和 branch ledger，选择下一轮 bounded branch experiment。",
        "Break down whether drawdown comes from time-window concentration, name concentration, or long holding tails.": "拆解回撤究竟来自时间窗口集中、个股集中，还是持有尾部过长。",
        "Run a finer root-cause diagnosis for": "先对",
        "before another automation iteration.": "做更细的根因诊断，再决定是否进入下一轮 automation iteration。",
        "Escalated blocker": "升级 blocker",
        "Escalated repeated blocker": "重复 blocker",
        "stop automatic retries, narrow the path, and write back the root-cause diagnosis before the next run.": "已停止自动重试，请收窄路径，并在下一次 run 前写回根因诊断。",
        "and stopped automatic retries.": "并已停止自动重试。",
        "Validated data coverage now clears the research-readiness gate, so promotion can evaluate strategy quality on the frozen universe definition.": "当前已验证数据覆盖已通过 research-readiness gate，promotion 可以在 frozen universe 定义下评估策略质量。",
        "Research inputs are ready, but the candidate still fails strategy-quality checks.": "研究输入已就绪，但候选仍未通过策略质量检查。",
        "Engineering guardrails work; promotion remains blocked on data readiness or the current research boundary.": "工程护栏正常，但 promotion 仍被数据就绪度或当前研究边界阻塞。",
        "Keep promotion honest by separating data-readiness blockers from strategy-quality blockers.": "把数据就绪 blocker 与策略质量 blocker 拆开判断，保持 promotion 结论诚实。",
        "Phase 1 Research OS - promotion evaluation": "Phase 1 Research OS - promotion 评估",
        "Phase 1 Research OS": "Phase 1 Research OS",
        "Keep the Phase 1 Research OS reproducible with tracked long-term memory and honest runtime artifacts.": "保持 Phase 1 Research OS 可复现，tracked long-term memory 与 runtime artifacts 分层清晰。",
        "Default project still lacks usable validated bars for the frozen universe.": "默认项目在 frozen universe 上仍缺少可用的 validated bars。",
        "Engineering guardrails work; real default-project research remains blocked on data coverage.": "工程护栏可用，但真实 default project 研究仍被数据覆盖率阻塞。",
        "Restore a usable validated bar snapshot for the frozen default universe.": "恢复 frozen default universe 可用的 validated bar 快照。",
        "Contract and dry-run orchestration tests passed in the repository virtual environment.": "仓库虚拟环境中的 contract 与 dry-run orchestration 测试已通过。",
        "Promotion on the default project is blocked by missing research inputs.": "默认项目的 promotion 仍被缺失研究输入阻塞。",
        "Tracked memory synced from config": "已从配置同步 tracked memory：",
        "Tracked memory sync refreshed for plan:": "Tracked memory 已按计划刷新：",
        "Keep the Phase 1 Research OS reproducible with tracked memory and honest runtime artifacts.": "保持 Phase 1 Research OS 可复现，tracked memory 与诚实的 runtime artifacts 保持一致。",
        "The long-term north star is still an autonomous quant research agent that can research, iterate, reflect, search for missing tools, operate tools, mine opportunities and factors, and use subagents adaptively.": "长期 north star 仍是一个能够自主研究、迭代、反思、搜索缺失工具、操作工具、挖掘机会与因子，并按需使用 subagents 的量化研究代理。",
        "Stage 0A completed by shrinking the default project from 3063 symbols to a data-ready 715-symbol range": "Stage 0A 已完成：默认项目已从 3063 个标的收缩到 715 个 data-ready 标的范围",
        "all stronger research claims must stay inside that restored range.": "所有更强的研究结论都必须限制在这块恢复后的范围内。",
        "The v1 core research pool is built from the restored 715-symbol range and currently keeps 492 mainboard names after ST, history, recent-volume, and liquidity filters.": "v1 核心研究池建立在恢复后的 715 标的范围上；在经过 ST、上市历史、近期成交量和流动性过滤后，当前保留 492 个主板标的。",
        "Architecture Slice 2 is now live: mission_tick writes mission, branch, and evidence ledgers, formal experiment JSON records, and real scout or implementer worker-task artifacts.": "Architecture Slice 2 已上线：`mission_tick` 会写入 mission、branch、evidence ledger，正式实验 JSON 记录，以及真实的 scout 或 implementer worker-task artifacts。",
        "agent_cycle is only a compatibility shell on top of mission_tick and must not overwrite the primary multi-branch mission state.": "`agent_cycle` 只是构建在 `mission_tick` 之上的兼容外壳，不能覆盖主多分支 mission state。",
        "Subagents are now a dynamic resource: the system should switch them on, downgrade them, pause them, or retire them according to real-time task needs instead of keeping them always active.": "Subagents 现在是动态资源：系统应按实时任务需要启用、降级、暂停或退役，而不是让它们始终保持 active。",
        "Worker subagent ids are collision-resistant so concurrent or closely spaced runs no longer reuse the same tracked id by accident.": "Worker subagent id 已具备抗碰撞能力，因此并发或相近时间的 run 不会再意外复用同一个 tracked id。",
        "Old strategy scripts still prefer the legacy project universe file when it exists, and only fall back to the new core pool when that file is missing": "旧策略脚本在 legacy project universe 文件存在时仍优先使用它，只有该文件缺失时才回退到新的 core pool",
        "this is an intentional compatibility bridge, not the final architecture.": "这是刻意保留的兼容桥，而不是最终架构。",
        "Promotion gate baseline wiring was repaired earlier, and this run completed the remaining benchmark fix by loading the configured benchmark series independently from ranked codes.": "promotion gate 的 baseline 接线此前已修复；本轮又补完了剩余 benchmark 修复，改为独立于 ranked codes 加载配置中的 benchmark 序列。",
        "On the current `as_share_research_v1` run, both `promote_candidate` and `agent_cycle --dry-run` now report `baselines_status=pass`, `benchmark_available=true`, and `equal_weight_available=true`.": "在当前 `as_share_research_v1` run 上，`promote_candidate` 和 `agent_cycle --dry-run` 都已报告 `baselines_status=pass`、`benchmark_available=true`、`equal_weight_available=true`。",
        "The stored readiness artifacts still classify the current 492-name core validated snapshot as ready for promotion-grade checks, so the live blocker is max drawdown 56.50% rather than generic missing bars or benchmark completeness.": "当前保存的 readiness artifacts 仍将 492 个标的的 core validated snapshot 归类为可进入 promotion-grade checks，因此当前真实 blocker 是 56.50% 的最大回撤，而不是泛化的缺 bars 或 benchmark 完整性问题。",
        "`equal_weight_total_return` remains `1.0497515982053982` after the benchmark repair, so the fix did not widen the equal-weight baseline definition.": "benchmark 修复后，`equal_weight_total_return` 仍保持 `1.0497515982053982`，说明这次修复没有扩大等权 baseline 的定义。",
        "Some readiness payloads still carry the legacy project label `2026Q1_limit_up` even though `as_share_research_v1` is now the live default-project name.": "尽管当前 live default-project 名称已经是 `as_share_research_v1`，部分 readiness payload 仍带着历史项目标签 `2026Q1_limit_up`。",
        "Do not describe queued verifier tasks as if full verification already happened.": "不要把仍在排队的 verifier 任务描述成已经完成了完整验证。",
        "Do not treat the 492-name core research pool as a drop-in replacement for every old strategy path before replacement tests are done.": "在替换测试完成前，不要把 492 标的的 core research pool 当作所有旧策略路径的直接替代物。",
        "Do not treat the current compatibility fallback in strategy scripts as a finished dual-pool migration.": "不要把策略脚本中当前的兼容性 fallback 当成已经完成的双池迁移。",
        "Do not keep subagents permanently active out of habit": "不要因为习惯就让 subagents 长期保持 active",
        "if a transient worker has finished, pause or retire it.": "如果某个临时 worker 已经完成，就应暂停或退役它。",
        "Do not run parallel top-level commands that write the same tracked project state as if they were concurrency-safe research execution.": "不要把会写入同一 tracked project state 的顶层命令并行运行，好像它们天然具备并发安全一样。",
        "Do not claim tool autonomy, multi-direction search, or profitable superagent behavior from Slice 2": "不要基于 Slice 2 宣称工具自治、多方向搜索或盈利性的 superagent 行为",
        "verifier execution is still partial and the strategy still fails promotion.": "当前 verifier 执行仍不完整，而且策略依然未通过 promotion。",
        "Do not reopen generic benchmark-missing diagnosis on `as_share_research_v1` unless `baselines_status` falls below `pass`": "除非 `baselines_status` 重新跌破 `pass`，否则不要在 `as_share_research_v1` 上重新打开泛化的 benchmark 缺失诊断",
        "that wiring bug is fixed.": "该接线问题已经修复。",
        "Do not rely on `python -m quant_mvp research_readiness` as a callable CLI step in the current build": "在当前构建中，不要依赖 `python -m quant_mvp research_readiness` 作为可直接调用的 CLI 步骤",
        "use the stored readiness artifacts or supported commands instead.": "请改用已保存的 readiness artifacts 或受支持的命令。",
        "Use STRATEGY_FAILURE_REPORT and the branch ledger to choose the first bounded drawdown-focused experiment now that baseline completeness passes.": "在 baseline 完整性已经通过后，使用 STRATEGY_FAILURE_REPORT 和 branch ledger 来选择第一条聚焦回撤的 bounded experiment。",
        "The limit-up screening path now shares one audited research core between the standalone script and the modular steps.": "limit-up screening 路径现在让 standalone script 与 modular steps 共享同一个经过审计的研究核心。",
        "Tracked long-term memory lives under `memory/projects/<project>/`; runtime artifacts stay under `data/` and `artifacts/`.": "tracked long-term memory 位于 `memory/projects/<project>/`；runtime artifacts 位于 `data/` 与 `artifacts/`。",
        "Default-project promotion is not trustworthy until validated bars exist for the frozen universe.": "在 frozen universe 具备 validated bars 之前，不要信任 default project 的 promotion 结论。",
        "Ignored runtime directories are not sufficient as the sole store for durable project memory.": "被忽略的 runtime 目录不能作为 durable project memory 的唯一存储。",
    "Restore validated default-project bars before trusting any research conclusion.": "在相信任何研究结论前，先恢复 default project 的 validated bars。",
    "Keep compact tracked ledgers and handoff files in sync with runtime experiment payloads.": "保持紧凑 tracked ledger 与 handoff 文件和 runtime experiment payloads 同步。",
    "ready coverage:": "已就绪覆盖：",
        "symbols with validated bars": "个标的具备已验证 bars",
        "raw_rows": "raw_rows",
        "cleaned_rows": "cleaned_rows",
        "validated_rows": "validated_rows",
        "Task breadth is below the minimum threshold for safe decomposition.": "任务广度尚未达到安全拆分的最低阈值。",
        "The work is still narrow enough for one integrating agent.": "当前工作仍足够单线，保持一个整合代理最稳妥。",
        "`promote_candidate` did not produce a new verified state change.": "`promote_candidate` 没有产出新的已验证状态变化。",
        "`data_validate` did not produce a new verified state change.": "`data_validate` 没有产出新的已验证状态变化。",
        "`agent_cycle_dry_run` did not produce a new verified state change.": "`agent_cycle_dry_run` 没有产出新的已验证状态变化。",
        "`research_audit` did not produce a new verified state change.": "`research_audit` 没有产出新的已验证状态变化。",
        "Auto-retired by iterative relevance review because the task no longer owns an independent work package.": "经过 iterative relevance review，任务已不再拥有独立工作包，相关 subagent 已自动退休。",
        "Auto-archived by iterative relevance review because the run is stopping and the task should not remain active.": "经过 iterative relevance review，run 即将停止，相关任务已自动归档而不再保持 active。",
        "Auto-canceled by iterative relevance review because the current direction superseded the old work package.": "经过 iterative relevance review，旧工作包已被当前方向替代，相关 subagent 已自动取消。",
        "Loop spawned a replacement subagent for the current bounded work package.": "loop 已为当前 bounded work package 新增替代 subagent。",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)

    text = re.sub(r"最大回撤 ([0-9.]+%) 高于 ([0-9.]+%)\.", r"最大回撤 \1 高于 \2。", text)
    text = re.sub(r"coverage_ratio=([0-9.]+)", r"coverage_ratio=\1", text)
    text = re.sub(r"`max_drawdown`", "`max_drawdown`", text)
    text = text.replace("; ", "；")
    return text
