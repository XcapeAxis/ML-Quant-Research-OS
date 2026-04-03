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
    "No recorded failures yet in this bootstrap state. Append new failures with root cause, corrective action, and current resolution status.": "当前 bootstrap 状态还没有失败记录。后续只追加高价值失败，并记录根因、纠正动作与当前处理状态。",
    "Subtasks are too coupled to split cleanly.": "子任务耦合度过高，暂不适合干净拆分。",
    "High coupling would turn subagents into coordination overhead.": "高耦合会让 subagents 只剩协调开销。",
    "File overlap is too high for efficient parallel work.": "文件重叠过高，不适合高效并行。",
    "The same hot files would need frequent merges, so splitting is suppressed.": "热点文件重叠严重，若拆分会频繁合并，因此抑制拆分。",
    "The coordination-adjusted score is too low.": "协调收益校正后的分数过低。",
    "Validation and isolation benefits do not yet offset decomposition cost.": "验证与隔离收益暂时还不足以覆盖拆分成本。",
    "Subagent policy files are unavailable.": "subagent policy 文件不可用。",
    "No subagents were activated.": "本轮没有启用额外 subagents。",
    "The default-project data blocker should be cleared before expanding into multiple subagents.": "默认项目的数据 blocker 还没清掉，现在扩成多 subagents 只会增加协作成本。",
    "The current default-project blocker does not justify extra coordination yet.": "当前默认项目 blocker 还不值得再增加一层协作。",
    "Stay effectively OFF until validated bars restore independent work packages.": "在 validated bars 恢复前，subagent 保持有效 OFF，先不要拆分。",
    "Gate is explicitly OFF.": "gate 被显式设为 OFF。",
    "Subagent decomposition is disabled for this task.": "当前任务禁用 subagent 拆分。",
    "Independent work packages exist and the coordination-adjusted score justifies controlled decomposition.": "独立工作包已经成立，协调校正后的收益支持受控拆分。",
    "Promotion gate diagnostics were generated and written to runtime artifacts.": "promotion gate 诊断已生成并写入 runtime artifacts。",
    "data_validate refreshed cleaned bars, coverage-gap artifacts, and research readiness.": "`data_validate` 已刷新 cleaned bars、coverage-gap artifacts 和 research readiness。",
    "data_validate refreshed readiness artifacts and tracked memory.": "`data_validate` 已刷新 readiness artifacts 和 tracked memory。",
    "Validated data recovery, coverage-gap analysis, and readiness writeback all executed.": "已执行已验证数据恢复、coverage-gap 分析与 readiness 写回。",
    "Promotion-grade research can proceed on the current validated snapshot.": "当前已验证快照已经满足 promotion-grade research 的前置条件。",
    "Coverage improved, but the readiness gate is still blocking broad research claims.": "覆盖率已有改善，但 readiness gate 仍阻止更广泛的研究结论。",
    "The repo truth still points to a data/readiness blocker, so the lowest-risk next action is to refresh validated inputs and readiness.": "当前 repo truth 仍指向数据或 readiness blocker，因此风险最低的下一步是刷新已验证输入与 readiness。",
    "Refresh coverage-gap and readiness artifacts, then rescan the blocker.": "刷新 coverage-gap 与 readiness artifacts，然后重新扫描 blocker。",
    "The current blocker is strategy- or gate-specific, so promotion diagnostics give the highest-signal next truth without widening the change set.": "当前 blocker 属于策略或 gate 维度，因此 promotion diagnostics 是不扩大变更面的最高信号下一步。",
    "Refresh the promotion gate and strategy failure report for the current research universe.": "刷新当前研究宇宙的 promotion gate 与策略失败报告。",
    "A control-plane rescan should start by refreshing the repo audit before another dry-run cycle.": "控制面重新扫描前，应先刷新 repo audit，再进入下一次 dry-run。",
    "Refresh audit docs and confirm the current repo boundary.": "刷新 audit 文档，并确认当前 repo 边界。",
    "After the current truth is refreshed, the next low-risk step is one dry-run control-plane cycle.": "当前 truth 刷新后，下一步风险最低的动作是一轮控制面的 dry-run cycle。",
    "Regenerate one bounded cycle record plus updated hypothesis and evaluation state.": "重新生成一条 bounded cycle 记录，并更新 hypothesis 与 evaluation 状态。",
    "Validated inputs and readiness improved enough to justify one more bounded iteration.": "已验证输入与 readiness 已改善到足以支撑再做一轮 bounded iteration。",
    "No additional unconfirmed questions have been recorded yet.": "当前尚未记录新的未确认问题。",
    "iterative_relevance_review": "迭代相关性复核",
    "Do not move durable memory back into ignored runtime directories.": "不要把 durable memory 再挪回被忽略的 runtime 目录。",
    "Do not trust default-project research claims until validated bars exist for the frozen universe.": "在 frozen universe 具备已验证 bars 前，不要相信 default project 的研究结论。",
    "Run the tracked-memory and contract test suite first.": "先跑 tracked-memory 与 contract 测试套件。",
    "verified_progress": "已验证进展",
    "blocker_clarified": "blocker 已澄清",
    "no_meaningful_progress": "没有显著进展",
    "direction_corrected": "方向已纠正",
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
    "retired": "已退役",
    "canceled": "已取消",
    "archived": "已归档",
    "refactored": "已重构",
    "proposed": "已提议",
}

_FRAGMENT_REPLACEMENTS = {
    "Max drawdown": "最大回撤",
    "exceeds": "高于",
    "Validated rows": "已验证行数",
    "are below the minimum readiness floor": "低于最小 readiness 下限",
    "Benchmark or equal-weight baselines are incomplete": "基准或等权基线不完整",
    "Promotion gate blocked the current candidate.": "当前候选仍被晋级门阻塞。",
    "Promotion gate blocked on strategy-quality checks.": "晋级门仍被策略质量检查阻塞。",
    "Promotion gate blocked on data readiness.": "晋级门仍被数据就绪度阻塞。",
    "Promotion gate blocked:": "晋级门阻塞：",
    "Resolve the failed gate reasons before the next promotion attempt.": "在下一次 promotion 前，先解决当前 gate 失败原因。",
    "Use the strategy failure report to design the next risk-focused experiment.": "基于策略失败报告设计下一轮聚焦风险的实验。",
    "Use STRATEGY_FAILURE_REPORT to design the next risk-focused experiment.": "基于 STRATEGY_FAILURE_REPORT 设计下一轮聚焦风险的实验。",
    "Use the strategy failure report and the branch ledger to choose the next bounded branch experiment.": "结合策略失败报告和 branch ledger，选择下一轮 bounded branch experiment。",
    "Break down whether drawdown comes from time-window concentration, name concentration, or long holding tails.": "拆解回撤究竟来自时间窗口集中、个股集中，还是持有尾部过长。",
    "Run a finer root-cause diagnosis for": "先对",
    "before another automation iteration.": "做更细的根因诊断，再决定是否进入下一轮自动化迭代。",
    "Escalated blocker": "升级 blocker",
    "Escalated repeated blocker": "重复 blocker 升级",
    "stop automatic retries, narrow the path, and write back the root-cause diagnosis before the next run.": "已停止自动重试，请收窄路径，并在下一次 run 前写回根因诊断。",
    "and stopped automatic retries.": "并已停止自动重试。",
    "Tracked memory bootstrap does not establish the current business blocker; refresh verified research artifacts before changing the narrative.": "tracked memory 初始化不会自动确定当前业务 blocker；变更叙事前先刷新已验证的研究 artifacts。",
    "Refresh the latest verified research artifacts before changing the blocker narrative.": "在修改 blocker 叙事之前，先刷新最新已验证的研究 artifacts。",
    "Tracked memory sync refreshed the current state only; it did not change the canonical blocker.": "tracked memory sync 只刷新了当前状态，没有改变 canonical blocker。",
    "Keep the current blocker diagnosis aligned across session_state and verifier artifacts.": "保持当前 blocker 诊断在 session_state 和 verifier artifacts 之间一致。",
    "Break down the current max-drawdown driver and compare one bounded challenger before rerunning the dry-run cycle.": "先拆解当前最大回撤驱动，再比较一个 bounded challenger，之后再重跑 dry-run cycle。",
    "Restore the validated snapshot and rerun the dry-run cycle only after the data boundary is healthy again.": "只在数据边界恢复健康后，再恢复 validated snapshot 并重跑 dry-run cycle。",
    "Refresh the blocker diagnosis and narrow one bounded next step before rerunning the dry-run cycle.": "在重跑 dry-run cycle 前，先刷新 blocker 诊断，并收窄到一个 bounded 下一步。",
    "Tracked memory synced from config": "已从配置同步 tracked memory",
    "Tracked memory sync refreshed for plan:": "Tracked memory 已按计划刷新：",
    "Keep the Phase 1 Research OS reproducible with tracked memory and honest runtime artifacts.": "保持 Phase 1 Research OS 可复现，并让 tracked memory 与 runtime artifacts 保持诚实一致。",
    "Keep the Phase 1 Research OS reproducible with tracked long-term memory and honest runtime artifacts.": "保持 Phase 1 Research OS 可复现，并让 tracked long-term memory 与 runtime artifacts 分层清晰。",
    "Contract and dry-run orchestration tests passed in the repository virtual environment.": "仓库虚拟环境中的 contract 与 dry-run orchestration 测试已通过。",
    "Restore a usable frozen universe plus local bars before rerunning the dry-run cycle.": "先恢复可用的 frozen universe 和本地 bars，再重跑 dry-run cycle。",
    "Restore a usable validated bar snapshot for the frozen default universe.": "恢复 frozen default universe 可用的 validated bar 快照。",
    "Use STRATEGY_FAILURE_REPORT and the branch ledger to choose the first bounded drawdown-focused experiment now that baseline completeness passes.": "既然 baseline 完整性已通过，就用 STRATEGY_FAILURE_REPORT 和 branch ledger 选择第一条聚焦 drawdown 的 bounded experiment。",
    "ready coverage:": "就绪覆盖：",
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

    for source, target in _FRAGMENT_REPLACEMENTS.items():
        text = text.replace(source, target)

    text = re.sub(r"最大回撤\s*([0-9.]+%)\s*高于\s*([0-9.]+%)\.", r"最大回撤 \1 高于 \2。", text)
    text = re.sub(r"已验证行数\s*([0-9]+)\s*低于最小 readiness 下限\s*([0-9]+)\.", r"已验证行数 \1 低于最小 readiness 下限 \2。", text)
    text = re.sub(r"coverage_ratio=([0-9.]+)", r"coverage_ratio=\1", text)
    text = text.replace("; ", "；")
    text = text.replace("。。", "。")
    return text
