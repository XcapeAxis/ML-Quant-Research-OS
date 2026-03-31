from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .localization import humanize_text


REQUIRED_CANDIDATE_FIELDS = [
    "strategy_id",
    "name",
    "category",
    "core_hypothesis",
    "economic_rationale",
    "required_data",
    "current_stage",
    "latest_action",
    "latest_result",
    "decision",
    "next_validation",
    "owner",
    "subagents_assigned",
    "artifact_refs",
    "blocked_by",
    "kill_criteria",
]

_CATEGORY_ZH = {
    "limit-up continuation": "limit-up continuation",
    "risk control": "risk control",
    "entry timing": "entry timing",
    "other": "other",
}

_STAGE_ZH = {
    "idea": "idea",
    "data-blocked": "data-blocked",
    "data-ready": "data-ready",
    "first-test": "first-test",
    "validation": "validation",
    "robustness": "robustness",
    "blocked": "blocked",
    "rejected": "rejected",
    "promoted": "promoted",
}

_DECISION_ZH = {
    "continue": "continue",
    "blocked": "blocked",
    "reject": "reject",
    "promote": "promote",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _clean_text(value: Any, default: str = "未记录") -> str:
    text = str(value or "").strip()
    return humanize_text(text) if text else default


def _optional_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"none", "null", "n/a"} else text


def _normalize_list(values: Any) -> list[str]:
    out: list[str] = []
    for item in values or []:
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in values:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _blocker_text(state: dict[str, Any]) -> str:
    return str(state.get("current_blocker", "")).strip()


def _looks_ready_data_status(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    return any(
        token in lowered
        for token in [
            "ready coverage",
            "validated snapshot",
            "promotion-grade",
            "validation-ready",
            "research-readiness",
            "已就绪覆盖",
            "可进入 promotion-grade",
        ]
    )


def _looks_explicit_data_blocker_text(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    return any(
        token in lowered
        for token in [
            "usable validated bars",
            "validated bars for the frozen universe",
            "missing research inputs",
            "missing validated inputs",
            "no validated bars",
            "coverage gap",
            "partial coverage",
            "readiness gate",
            "research-readiness gate",
            "data readiness",
            "可用日频",
            "缺少研究输入",
            "缺少可用的 validated",
            "缺少可用的已验证",
            "无可用",
            "覆盖缺口",
            "覆盖率不足",
            "数据就绪",
        ]
    )


def _looks_non_data_blocker_text(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    return any(
        token in lowered
        for token in [
            "drawdown",
            "回撤",
            "leakage",
            "walk-forward",
            "walk forward",
            "baseline",
            "benchmark",
            "rank dataframe is empty",
            "empty rank",
            "branch pool",
            "ranking contract",
            "selection contract",
            "策略质量",
            "契约",
            "verifier",
            "factor",
            "feature",
            "label",
            "model",
        ]
    )


def _is_data_blocked(state: dict[str, Any]) -> bool:
    blocker = _blocker_text(state)
    readiness = str((state.get("verify_last", {}) or {}).get("default_project_data_status", "")).strip()
    if _looks_non_data_blocker_text(blocker):
        return False
    if _looks_ready_data_status(readiness):
        return False
    if state.get("data_ready") is True:
        return False
    if _looks_explicit_data_blocker_text(blocker):
        return True
    readiness_lower = readiness.lower()
    if any(token in readiness_lower for token in ["missing", "partial", "pilot", "blocked", "unavailable", "coverage gap", "not ready"]):
        return True
    data_ready = state.get("data_ready")
    return data_ready is False


def _is_drawdown_blocked(state: dict[str, Any]) -> bool:
    blocker = _blocker_text(state).lower()
    return "drawdown" in blocker or "回撤" in blocker


def _default_required_data() -> str:
    return "主板 A 股日频 OHLCV、上市天数、ST/板块过滤、涨停代理、下个交易日收益、基准与等权基线。"


def _variant_blueprint(strategy_id: str) -> dict[str, Any]:
    blueprints = {
        "baseline_limit_up": {
            "track": "primary",
            "name": "涨停主线基线分支",
            "category": "limit-up continuation",
            "core_hypothesis": "过去一段时间反复出现涨停、随后回到突破起点附近的主板个股，后续更容易再次走强；先把这条主线稳定保存成基线，再评估其它改法。",
            "economic_rationale": "A 股主板里的涨停通常意味着资金短时间集中抢筹。若个股涨停后没有彻底转弱，而是在突破起点附近重新整理，说明强势资金可能仍在，后续二次启动概率更高；保留基线则能判断后续改动到底是在修复风险还是只是在制造噪音。",
            "required_data": _default_required_data(),
            "kill_criteria": "如果可用输入恢复后，这条主线在泄漏、可交易性、walk-forward 与成本压力检查下仍无法把最大回撤压到 30% 以内，就停止继续把它当主线。",
            "fallback_latest_action": "已建立主线基线候选，当前等待新的有界验证。",
            "fallback_latest_result": "已有主线候选池与实验记录，但没有新的通过结论。",
            "next_validation_data_blocked": "先恢复可用日频 bars，再对主线做第一轮有界验证。",
            "next_validation_drawdown": "先拆解主线回撤是时间集中、个股集中还是持有尾部过长，再决定优先上风控分支还是收紧入场分支。",
            "next_validation_ready": "继续围绕主线做 bounded validation，并把 blocker 直接写回卡片和看板。",
        },
        "risk_constrained_limit_up": {
            "track": "secondary",
            "name": "涨停主线风控分支",
            "category": "risk control",
            "core_hypothesis": "在不破坏涨停回踩再启动这个主线定义的前提下，更严格的止损、市场过滤或持仓约束可以显著降低回撤。",
            "economic_rationale": "如果主线 alpha 来自强势股二次启动，而不是单纯硬扛波动，那么更强的风险约束应该先砍掉最差交易，同时保住大部分有效信号。",
            "required_data": _default_required_data(),
            "kill_criteria": "如果回撤改善很弱、但收益和通过率明显恶化，就停止继续扩大这条风控分支。",
            "fallback_latest_action": "已列为支线分支，等待主线 blocker 收敛后再做对照验证。",
            "fallback_latest_result": "风控分支的研究问题明确，但还没有最新验证结论。",
            "next_validation_data_blocked": "先恢复主线可用输入；输入没恢复前，这条分支不值得单独开跑。",
            "next_validation_drawdown": "拿主线失败样本做回撤分解，确认是否值得优先把风控分支推到第一轮真实验证。",
            "next_validation_ready": "在和主线完全同一批输入上做对照验证，只看回撤改善是否值得继续。",
        },
        "tighter_entry_limit_up": {
            "track": "secondary",
            "name": "涨停主线收紧入场分支",
            "category": "entry timing",
            "core_hypothesis": "把入选阈值收紧，只保留更接近再次启动位置的个股，可以减少过早买入带来的假突破和大回撤。",
            "economic_rationale": "如果真正的二次启动往往发生在更接近突破起点、筹码更集中的位置，那么收紧入场条件应该先减少质量差的提前埋伏。",
            "required_data": _default_required_data(),
            "kill_criteria": "如果收紧入场后只是在减少交易次数，却没有改善回撤或收益质量，就停止继续扩展这条分支。",
            "fallback_latest_action": "已列为支线分支，等待主线 blocker 收敛后再做对照验证。",
            "fallback_latest_result": "入场收紧分支的研究问题明确，但还没有最新验证结论。",
            "next_validation_data_blocked": "先恢复主线可用输入；输入没恢复前，这条分支不值得单独开跑。",
            "next_validation_drawdown": "先确认主线失败是否主要来自入场过早，再决定是否优先验证这条分支。",
            "next_validation_ready": "用和主线相同的输入做 bounded validation，判断它是否真的减少了早进场造成的回撤。",
        },
        "legacy_single_branch": {
            "track": "rejected",
            "name": "旧单分支兼容路径",
            "category": "other",
            "core_hypothesis": "先把旧 `agent_cycle` 兼容跑通，再谈更复杂的多分支研究。",
            "economic_rationale": "这不是市场行为假设，只是为了兼容旧控制面而保留的一条过渡路径。",
            "required_data": "无额外市场数据要求；它主要依赖旧控制面的兼容行为。",
            "kill_criteria": "只要旧单分支兼容不再是必须前提，就不要再把它当作策略研究候选。",
            "fallback_latest_action": "已从策略研究主线移除，仅保留为兼容历史记录。",
            "fallback_latest_result": "它没有新的策略研究价值，不再占用研究主线。",
            "next_validation_data_blocked": "无；除非再次出现必须回退旧 `agent_cycle` 的兼容问题。",
            "next_validation_drawdown": "无；它不是为了解决当前主线回撤问题而保留的。",
            "next_validation_ready": "无；除非再次需要排查旧单分支兼容行为。",
        },
        "limit_up_screening_mainline": {
            "track": "primary",
            "name": "涨停回踩再启动主线",
            "category": "limit-up continuation",
            "core_hypothesis": "过去一段时间反复出现涨停、随后回到突破起点附近的主板个股，后续更容易再次走强。",
            "economic_rationale": "涨停代表短时间内的强资金拥挤。如果涨停后回调没有破坏核心结构，而是在突破起点附近重新企稳，说明强势资金可能仍在，后续二次启动概率更高。",
            "required_data": _default_required_data(),
            "kill_criteria": "如果在真实可用输入上反复验证后，这条主线仍无法通过基本风控与晋级门槛，就停止继续把它当主线。",
            "fallback_latest_action": "已创建 canonical seed candidate，等待第一轮有界验证。",
            "fallback_latest_result": "主线对象已显式化，但还没有新的实质验证结论。",
            "next_validation_data_blocked": "先恢复可用日频 bars，再推进第一轮验证。",
            "next_validation_drawdown": "先拆解回撤根因，再决定是否走风控分支或收紧入场分支。",
            "next_validation_ready": "继续推进第一轮有界验证，并把结论写回主线卡片。",
        },
    }
    return dict(blueprints.get(strategy_id, blueprints["limit_up_screening_mainline"]))


def _latest_branch_records(path: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(path):
        branch_id = str(row.get("branch_id", "")).strip()
        if branch_id:
            latest[branch_id] = row
    return latest


def _latest_evidence_records(path: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(path):
        branch_id = str(row.get("branch_id", "")).strip()
        if branch_id:
            latest[branch_id] = row
    return latest


def _infer_subagent_strategy_id(record: dict[str, Any]) -> str | None:
    direct = _optional_text(record.get("strategy_id"))
    if direct:
        return direct
    branch_id = _optional_text(record.get("branch_id"))
    if branch_id:
        return branch_id
    candidate_id = _optional_text(record.get("candidate_id"))
    if candidate_id.startswith("candidate::"):
        return candidate_id.split("::", 1)[1].strip() or None
    return None


def _active_strategy_subagents(state: dict[str, Any], strategy_id: str) -> list[str]:
    assigned: list[str] = []
    for record in state.get("subagents", []) or []:
        if record.get("status") not in {"active", "blocked"}:
            continue
        if _infer_subagent_strategy_id(record) == strategy_id:
            subagent_id = str(record.get("subagent_id", "")).strip()
            if subagent_id:
                assigned.append(subagent_id)
    return _dedupe_keep_order(assigned)


def _candidate_status(strategy_id: str, state: dict[str, Any], *, track: str) -> tuple[str, str, list[str]]:
    blocker = _clean_text(_blocker_text(state))
    if track == "rejected":
        return "rejected", "reject", ["它只是旧控制面兼容路径，不再作为策略研究主线。"]
    if _is_data_blocked(state):
        return "data-blocked", "blocked", [blocker]
    if _is_drawdown_blocked(state):
        return "validation", "blocked", [blocker]
    if blocker and blocker.lower() not in {"none", "unknown"}:
        return "blocked", "blocked", [blocker]
    if "promote" in str(state.get("last_verified_capability", "")).lower():
        return "promoted", "promote", []
    if strategy_id == "baseline_limit_up":
        return "first-test", "continue", []
    return "idea", "continue", []


def _candidate_latest_action(
    strategy_id: str,
    state: dict[str, Any],
    blueprint: dict[str, Any],
    branch_record: dict[str, Any] | None,
    evidence_record: dict[str, Any] | None,
) -> str:
    if evidence_record:
        worker_tasks = list(evidence_record.get("worker_tasks", []) or [])
        verified_roles = [str(item.get("role", "")).strip() for item in worker_tasks if item.get("state") == "verified"]
        queued_roles = [str(item.get("role", "")).strip() for item in worker_tasks if item.get("state") == "queued"]
        if verified_roles or queued_roles:
            parts: list[str] = []
            if verified_roles:
                parts.append(f"最近一次记录里，{strategy_id} 已完成 {'/'.join(verified_roles)} 资料整理")
            if queued_roles:
                parts.append(f"{'/'.join(queued_roles)} 仍未真正开始有界验证")
            return "；".join(parts) + "。"
    if branch_record:
        return _clean_text(branch_record.get("objective"), blueprint.get("fallback_latest_action", "未记录"))
    return _clean_text(blueprint.get("fallback_latest_action"))


def _candidate_latest_result(
    strategy_id: str,
    state: dict[str, Any],
    blueprint: dict[str, Any],
    evidence_record: dict[str, Any] | None,
    decision: str,
) -> str:
    if evidence_record:
        worker_tasks = list(evidence_record.get("worker_tasks", []) or [])
        queued_verifier = any(str(item.get("role", "")).strip() == "verifier" and item.get("state") == "queued" for item in worker_tasks)
        if queued_verifier:
            return f"{strategy_id} 目前只有候选池与实验记录，真正的 verifier 结论仍缺失。"
    if decision == "reject":
        return "它不再代表独立的策略研究问题，只保留历史兼容意义。"
    if decision == "blocked":
        return f"当前没有新的通过结论；主要被 `{_clean_text(_blocker_text(state))}` 卡住。"
    return _clean_text(blueprint.get("fallback_latest_result"))


def _candidate_next_validation(blueprint: dict[str, Any], state: dict[str, Any], *, decision: str) -> str:
    if decision == "reject":
        return _clean_text(blueprint.get("next_validation_ready", "无"))
    if _is_data_blocked(state):
        return _clean_text(blueprint.get("next_validation_data_blocked"))
    if _is_drawdown_blocked(state):
        return _clean_text(blueprint.get("next_validation_drawdown"))
    return _clean_text(blueprint.get("next_validation_ready"))


def _candidate_artifacts(
    *,
    blueprint: dict[str, Any],
    branch_record: dict[str, Any] | None,
    evidence_record: dict[str, Any] | None,
    paths,
) -> list[str]:
    refs: list[str] = []
    if evidence_record:
        refs.append(str(paths.evidence_ledger_path))
        refs.extend(_normalize_list(evidence_record.get("artifact_refs")))
        experiment_path = str(evidence_record.get("experiment_record_path", "")).strip()
        if experiment_path:
            refs.append(experiment_path)
    if branch_record:
        refs.append(str(paths.branch_ledger_path))
        snapshot_id = str(branch_record.get("branch_pool_snapshot_id", "")).strip()
        if snapshot_id:
            refs.append(snapshot_id)
    return _dedupe_keep_order([item for item in refs if item])


def _candidate_from_blueprint(
    *,
    strategy_id: str,
    state: dict[str, Any],
    paths,
    branch_record: dict[str, Any] | None = None,
    evidence_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blueprint = _variant_blueprint(strategy_id)
    stage, decision, blocked_by = _candidate_status(strategy_id, state, track=str(blueprint.get("track", "secondary")))
    subagents_assigned = _active_strategy_subagents(state, strategy_id)
    owner = subagents_assigned[0] if len(subagents_assigned) == 1 else "main"
    return {
        "strategy_id": strategy_id,
        "track": str(blueprint.get("track", "secondary")),
        "name": str(blueprint.get("name", strategy_id)),
        "category": str(blueprint.get("category", "other")),
        "core_hypothesis": str(blueprint.get("core_hypothesis", "")),
        "economic_rationale": str(blueprint.get("economic_rationale", "")),
        "required_data": str(blueprint.get("required_data", _default_required_data())),
        "current_stage": stage,
        "latest_action": _candidate_latest_action(strategy_id, state, blueprint, branch_record, evidence_record),
        "latest_result": _candidate_latest_result(strategy_id, state, blueprint, evidence_record, decision),
        "decision": decision,
        "next_validation": _candidate_next_validation(blueprint, state, decision=decision),
        "owner": owner,
        "subagents_assigned": subagents_assigned,
        "artifact_refs": _candidate_artifacts(
            blueprint=blueprint,
            branch_record=branch_record,
            evidence_record=evidence_record,
            paths=paths,
        ),
        "blocked_by": blocked_by,
        "kill_criteria": str(blueprint.get("kill_criteria", "")),
    }


def _generated_candidates(state: dict[str, Any], paths) -> list[dict[str, Any]]:
    branch_records = _latest_branch_records(paths.branch_ledger_path)
    evidence_records = _latest_evidence_records(paths.evidence_ledger_path)
    if not branch_records:
        return [
            _candidate_from_blueprint(
                strategy_id="limit_up_screening_mainline",
                state=state,
                paths=paths,
            ),
        ]

    order = ["baseline_limit_up", "risk_constrained_limit_up", "tighter_entry_limit_up", "legacy_single_branch"]
    for branch_id in branch_records:
        if branch_id not in order:
            order.append(branch_id)
    return [
        _candidate_from_blueprint(
            strategy_id=strategy_id,
            state=state,
            paths=paths,
            branch_record=branch_records.get(strategy_id),
            evidence_record=evidence_records.get(strategy_id),
        )
        for strategy_id in order
    ]


def _normalize_candidate(candidate: dict[str, Any], *, state: dict[str, Any], paths) -> dict[str, Any]:
    strategy_id = str(candidate.get("strategy_id", "")).strip() or "limit_up_screening_mainline"
    generated = _candidate_from_blueprint(strategy_id=strategy_id, state=state, paths=paths)
    merged = dict(generated)
    merged.update({key: value for key, value in candidate.items() if value not in (None, "")})
    merged["strategy_id"] = strategy_id
    merged["subagents_assigned"] = _normalize_list(merged.get("subagents_assigned"))
    merged["artifact_refs"] = _normalize_list(merged.get("artifact_refs"))
    merged["blocked_by"] = _normalize_list(merged.get("blocked_by"))
    merged["owner"] = str(merged.get("owner", "main")).strip() or "main"
    return merged


def _resolved_strategy_focus(state: dict[str, Any], *, summary: dict[str, Any]) -> list[str]:
    valid_ids = {
        str(item.get("strategy_id", "")).strip()
        for item in state.get("strategy_candidates", [])
        if isinstance(item, dict) and str(item.get("strategy_id", "")).strip()
    }
    requested_focus = [
        str(item).strip()
        for item in list(state.get("current_strategy_focus", []) or [])
        if str(item).strip() and str(item).strip() in valid_ids
    ]
    if requested_focus:
        seen: set[str] = set()
        deduped: list[str] = []
        for strategy_id in requested_focus:
            if strategy_id in seen:
                continue
            seen.add(strategy_id)
            deduped.append(strategy_id)
        return deduped[:3]
    return summary["primary_ids"][:3]


def ensure_strategy_visibility_state(state: dict[str, Any], *, paths) -> dict[str, Any]:
    updated = dict(state)
    current_candidates = list(updated.get("strategy_candidates", []) or [])
    if current_candidates:
        candidates = [_normalize_candidate(dict(item), state=updated, paths=paths) for item in current_candidates if isinstance(item, dict)]
    else:
        candidates = _generated_candidates(updated, paths)
    updated["strategy_candidates"] = candidates
    summary = summarize_strategy_visibility(updated)
    updated["current_research_cycle_type"] = summary["round_type"]
    updated["current_primary_strategy_ids"] = summary["primary_ids"]
    updated["current_secondary_strategy_ids"] = summary["secondary_ids"]
    updated["current_blocked_strategy_ids"] = summary["blocked_ids"]
    updated["current_rejected_strategy_ids"] = summary["rejected_ids"]
    updated["current_promoted_strategy_ids"] = summary["promoted_ids"]
    updated["current_strategy_focus"] = _resolved_strategy_focus(updated, summary=summary)
    updated["current_strategy_summary"] = summary["strategy_line"]
    return updated


def summarize_strategy_visibility(state: dict[str, Any]) -> dict[str, Any]:
    candidates = [dict(item) for item in state.get("strategy_candidates", []) if isinstance(item, dict)]
    primary = [item for item in candidates if item.get("track") == "primary"]
    secondary = [item for item in candidates if item.get("track") == "secondary"]
    blocked = [item for item in candidates if item.get("decision") == "blocked"]
    rejected = [item for item in candidates if item.get("decision") == "reject"]
    promoted = [item for item in candidates if item.get("decision") == "promote"]
    round_type = "基础设施恢复轮" if _is_data_blocked(state) else "策略推进轮"
    primary_names = [f"{item['strategy_id']}（{item['name']}）" for item in primary[:3]]
    secondary_names = [f"{item['strategy_id']}（{item['name']}）" for item in secondary[:3]]
    blocked_names = [f"{item['strategy_id']}（{item['name']}）" for item in blocked[:5]]
    rejected_names = [f"{item['strategy_id']}（{item['name']}）" for item in rejected[:5]]
    promoted_names = [f"{item['strategy_id']}（{item['name']}）" for item in promoted[:5]]
    blocker = _clean_text(_blocker_text(state))
    if round_type == "基础设施恢复轮":
        strategy_line = f"本轮未进行实质策略研究，原因是 {blocker}；当前先恢复研究前提并保持策略对象可见。"
        system_line = "本轮主要在修正研究前提、统一项目身份和补齐研究记录展示，没有新增策略验证。"
    else:
        focus = primary_names[0] if primary_names else "主线策略"
        strategy_line = f"本轮围绕 {focus} 继续收敛研究阻塞；当前最硬的限制仍是 {blocker}。"
        system_line = "本轮主要把当前研究结论、阻塞原因和后续验证顺序写清楚，没有新增宽泛系统扩张。"
    return {
        "round_type": round_type,
        "system_line": system_line,
        "strategy_line": strategy_line,
        "primary": primary,
        "secondary": secondary,
        "blocked": blocked,
        "rejected": rejected,
        "promoted": promoted,
        "primary_ids": [item["strategy_id"] for item in primary],
        "secondary_ids": [item["strategy_id"] for item in secondary],
        "blocked_ids": [item["strategy_id"] for item in blocked],
        "rejected_ids": [item["strategy_id"] for item in rejected],
        "promoted_ids": [item["strategy_id"] for item in promoted],
        "primary_names": primary_names,
        "secondary_names": secondary_names,
        "blocked_names": blocked_names,
        "rejected_names": rejected_names,
        "promoted_names": promoted_names,
    }


def render_strategy_board(state: dict[str, Any], *, paths) -> str:
    summary = summarize_strategy_visibility(state)
    blocker = _clean_text(_blocker_text(state))
    primary = summary.get("primary_names") or ["尚未记录"]
    secondary = summary.get("secondary_names") or ["当前为空"]
    blocked = summary.get("blocked_names") or ["当前为空"]
    rejected = summary.get("rejected_names") or ["当前为空"]
    promoted = summary.get("promoted_names") or ["当前为空"]
    lines = [
        "# 策略研究看板",
        "",
        "## 主线策略",
        f"- 当前主线策略: {', '.join(primary)}",
        f"- 当前轮次类型: {summary['round_type']}",
        f"- 当前 blocker: {blocker}",
        f"- 当前策略推进判断: {summary['strategy_line']}",
        "",
        "## 支线策略",
        f"- 当前支线策略: {', '.join(secondary)}",
        f"- blocked 策略: {', '.join(blocked)}",
        f"- rejected 策略: {', '.join(rejected)}",
        f"- promoted 策略: {', '.join(promoted)}",
        "",
        "## 系统判断",
        f"- 系统推进判断: {summary['system_line']}",
        "- 说明: 这里只展示当前研究分支、阻塞项和下一步顺序，不再回退到旧重置模板。",
        "",
        "## 相关 tracked memory",
        f"- strategy_board: {paths.strategy_board_path}",
        f"- strategy_candidates_dir: {paths.strategy_candidates_dir}",
        f"- strategy_action_log: {paths.strategy_action_log_path}",
        f"- research_activity: {paths.research_activity_path}",
        f"- idea_backlog: {paths.idea_backlog_path}",
        f"- research_progress: {paths.research_progress_path}",
    ]
    return "\n".join(lines)

def render_strategy_candidate_card(candidate: dict[str, Any]) -> str:
    lines = [
        f"# {candidate['name']}",
        "",
        f"- strategy_id: {candidate['strategy_id']}",
        f"- name: {candidate['name']}",
        f"- category: {_CATEGORY_ZH.get(candidate['category'], candidate['category'])}",
        f"- core_hypothesis: {candidate['core_hypothesis']}",
        f"- economic_rationale: {candidate['economic_rationale']}",
        f"- required_data: {candidate['required_data']}",
        f"- current_stage: {candidate['current_stage']}",
        f"- latest_action: {candidate['latest_action']}",
        f"- latest_result: {candidate['latest_result']}",
        f"- decision: {candidate['decision']}",
        f"- next_validation: {candidate['next_validation']}",
        f"- owner: {candidate['owner']}",
        "- subagents_assigned:",
    ]
    lines.extend([f"  - {item}" for item in candidate["subagents_assigned"]] or ["  - none"])
    lines.append("- artifact_refs:")
    lines.extend([f"  - {item}" for item in candidate["artifact_refs"]] or ["  - none"])
    lines.append("- blocked_by:")
    lines.extend([f"  - {item}" for item in candidate["blocked_by"]] or ["  - none"])
    lines.append(f"- kill_criteria: {candidate['kill_criteria']}")
    return "\n".join(lines)


def render_strategy_progress(state: dict[str, Any]) -> str:
    summary = summarize_strategy_visibility(state)
    lines = [
        "# 研究推进",
        "",
        f"- 当前轮次类型: {summary['round_type']}",
        f"- 系统推进: {summary['system_line']}",
        f"- 策略推进: {summary['strategy_line']}",
        f"- 当前主线策略: {', '.join(summary['primary_names']) or '尚未记录'}",
        f"- 当前 blocker: {_clean_text(_blocker_text(state))}",
        f"- 当前 blocked 策略: {', '.join(summary['blocked_names']) or '当前为空'}",
        f"- 当前 rejected 策略: {', '.join(summary['rejected_names']) or '当前为空'}",
        f"- 下一步建议: {_clean_text(state.get('next_priority_action'))}",
    ]
    return "\n".join(lines)


def render_strategy_cards(state: dict[str, Any], *, paths) -> dict[Path, str]:
    cards: dict[Path, str] = {}
    for candidate in state.get("strategy_candidates", []) or []:
        if not isinstance(candidate, dict):
            continue
        strategy_id = str(candidate.get("strategy_id", "")).strip()
        if not strategy_id:
            continue
        cards[paths.strategy_candidates_dir / f"{strategy_id}.md"] = render_strategy_candidate_card(candidate)
    return cards
