from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .localization import humanize_text
from ..project_identity import CANONICAL_PROJECT_ID


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


def _clean_text(value: Any, default: str = "Not recorded.") -> str:
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


def _project_id_from_state(state: dict[str, Any]) -> str:
    return (
        _optional_text(state.get("canonical_project_id"))
        or _optional_text(state.get("project"))
        or CANONICAL_PROJECT_ID
    )


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
            "data-ready",
            "ready",
        ]
    )


def _looks_explicit_data_blocker_text(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    return any(
        token in lowered
        for token in [
            "usable raw bars",
            "usable validated bars",
            "validated rows",
            "validated bars for the frozen universe",
            "missing research inputs",
            "missing validated inputs",
            "no validated bars",
            "coverage gap",
            "partial coverage",
            "readiness gate",
            "research-readiness gate",
            "data readiness",
            "funding coverage",
            "instrument metadata",
            "fees not modeled",
            "missing funding",
            "missing fee",
            "minimum readiness floor",
        ]
    )


def _looks_non_data_blocker_text(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    return any(
        token in lowered
        for token in [
            "drawdown",
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
            "factor",
            "feature",
            "signal",
            "model",
            "postmortem",
        ]
    )


def _is_data_blocked(state: dict[str, Any]) -> bool:
    blocker = _blocker_text(state)
    readiness = str((state.get("verify_last", {}) or {}).get("default_project_data_status", "")).strip()
    project_id = _project_id_from_state(state)
    if _looks_non_data_blocker_text(blocker):
        return False
    if _looks_ready_data_status(readiness):
        return False
    if state.get("data_ready") is True:
        return False
    if project_id == CANONICAL_PROJECT_ID and readiness.lower() in {"", "unknown", "none"}:
        return True
    if _looks_explicit_data_blocker_text(blocker):
        return True
    readiness_lower = readiness.lower()
    if any(
        token in readiness_lower
        for token in ["missing", "partial", "pilot", "blocked", "unavailable", "coverage gap", "not ready"]
    ):
        return True
    return state.get("data_ready") is False


def _is_drawdown_blocked(state: dict[str, Any]) -> bool:
    return "drawdown" in _blocker_text(state).lower()


def _crypto_required_data() -> str:
    return (
        "OKX instrument metadata, OHLCV, funding rate, fee model, contract specs, and a validated universe snapshot "
        "for the frozen research set."
    )


def _legacy_required_data() -> str:
    return "Legacy A-share data only. This branch is archived and should not drive the active research loop."


def _crypto_blueprints() -> dict[str, dict[str, Any]]:
    return {
        "okx_phase0_research_mainline": {
            "track": "primary",
            "name": "OKX phase-0 research mainline",
            "category": "market-structure",
            "core_hypothesis": (
                "A small, validated OKX universe plus explicit fee and funding modeling is enough to prove whether the "
                "research loop can produce honest, repeatable evidence."
            ),
            "economic_rationale": (
                "The first job is not alpha maximization. It is to show that the crypto research process can survive data "
                "quality checks, cost modeling, walk-forward review, and postmortem discipline."
            ),
            "required_data": _crypto_required_data(),
            "kill_criteria": (
                "Stop treating this as the mainline if repeatable phase-0 experiments still cannot produce a trustworthy "
                "evaluation bundle after data, fee, and funding inputs are restored."
            ),
            "fallback_latest_action": "Keep the crypto phase-0 hypothesis queue narrow and rebuild missing OKX inputs first.",
            "fallback_latest_result": "The mainline exists, but it is still waiting for a truthful validation cycle.",
            "next_validation_data_blocked": "Restore usable OKX inputs and materialize the frozen universe before rerunning research checks.",
            "next_validation_drawdown": "Hold promotion and inspect whether cost, funding, or walk-forward weakness is driving the failure.",
            "next_validation_ready": "Run the next bounded experiment bundle and write the evidence back into tracked memory.",
        },
        "okx_cost_funding_guardrail": {
            "track": "secondary",
            "name": "OKX cost and funding guardrail",
            "category": "risk-control",
            "core_hypothesis": (
                "Many early crypto research wins disappear once fees, funding, and contract details are modeled honestly. "
                "This branch exists to prove or reject that risk early."
            ),
            "economic_rationale": (
                "Crypto backtests are easy to overstate when funding or fee drag is missing. This branch prevents false "
                "confidence from leaking into promotion decisions."
            ),
            "required_data": _crypto_required_data(),
            "kill_criteria": "Drop this branch only after fees and funding are fully modeled in the mainline and no longer need a separate guardrail.",
            "fallback_latest_action": "Keep this branch as a standing check on all promising OKX experiments.",
            "fallback_latest_result": "The guardrail is defined, but it still needs real experiment evidence.",
            "next_validation_data_blocked": "Do not run this branch until funding and fee inputs are available for the frozen OKX universe.",
            "next_validation_drawdown": "Compare funding- and fee-aware results against the raw mainline result before any promotion.",
            "next_validation_ready": "Re-run the candidate with explicit cost and funding terms and record the delta.",
        },
        "legacy_a_share_archive": {
            "track": "rejected",
            "name": "Legacy A-share archive",
            "category": "legacy",
            "core_hypothesis": "This is a historical reference only. It is not an active research branch.",
            "economic_rationale": "Keep the old work visible for reference, but do not let it steer the active crypto program.",
            "required_data": _legacy_required_data(),
            "kill_criteria": "Never promote this branch back into the active crypto workflow without an explicit strategic reset.",
            "fallback_latest_action": "Leave this branch archived and keep it out of the active research queue.",
            "fallback_latest_result": "Legacy material remains available, but it is not part of the active decision loop.",
            "next_validation_data_blocked": "None. This branch should stay archived.",
            "next_validation_drawdown": "None. This branch should stay archived.",
            "next_validation_ready": "None. This branch should stay archived.",
        },
    }


def _legacy_blueprints() -> dict[str, dict[str, Any]]:
    return {
        "limit_up_screening_mainline": {
            "track": "primary",
            "name": "Legacy A-share mainline",
            "category": "legacy",
            "core_hypothesis": "Legacy A-share research path kept only for backward compatibility.",
            "economic_rationale": "This branch is preserved so historical memory files remain interpretable.",
            "required_data": _legacy_required_data(),
            "kill_criteria": "Keep archived unless the strategy program explicitly returns to A-share as the active market focus.",
            "fallback_latest_action": "Treat this branch as legacy and avoid expanding it.",
            "fallback_latest_result": "This branch exists only as historical context.",
            "next_validation_data_blocked": "None.",
            "next_validation_drawdown": "None.",
            "next_validation_ready": "None.",
        }
    }


def _blueprints_for_project(project_id: str) -> dict[str, dict[str, Any]]:
    return _crypto_blueprints() if project_id == CANONICAL_PROJECT_ID else _legacy_blueprints()


def _default_strategy_id(project_id: str) -> str:
    return "okx_phase0_research_mainline" if project_id == CANONICAL_PROJECT_ID else "limit_up_screening_mainline"


def _variant_blueprint(strategy_id: str, *, project_id: str) -> dict[str, Any]:
    blueprints = _blueprints_for_project(project_id)
    return dict(blueprints.get(strategy_id, blueprints[_default_strategy_id(project_id)]))


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


def _candidate_status(
    strategy_id: str,
    state: dict[str, Any],
    *,
    track: str,
) -> tuple[str, str, list[str]]:
    blocker = _clean_text(_blocker_text(state))
    if track == "rejected":
        return "archived", "reject", ["Legacy reference only."]
    if _is_data_blocked(state):
        return "data-blocked", "blocked", [blocker]
    if _is_drawdown_blocked(state):
        return "validation", "blocked", [blocker]
    if blocker and blocker.lower() not in {"none", "unknown", "not recorded."}:
        return "blocked", "blocked", [blocker]
    if "promote" in str(state.get("last_verified_capability", "")).lower():
        return "promoted", "promote", []
    if strategy_id == _default_strategy_id(_project_id_from_state(state)):
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
                parts.append(f"{strategy_id} already has verified work from {'/'.join(verified_roles)}")
            if queued_roles:
                parts.append(f"{'/'.join(queued_roles)} is still queued")
            return ". ".join(parts) + "."
    if branch_record:
        return _clean_text(branch_record.get("objective"), blueprint.get("fallback_latest_action", "Not recorded."))
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
        queued_verifier = any(
            str(item.get("role", "")).strip() == "verifier" and item.get("state") == "queued"
            for item in worker_tasks
        )
        if queued_verifier:
            return f"{strategy_id} has a candidate record, but the verifier conclusion is still missing."
    if decision == "reject":
        return "This branch is archived and should not steer the active research loop."
    if decision == "blocked":
        return f"No passing conclusion yet. Current blocker: {_clean_text(_blocker_text(state))}"
    return _clean_text(blueprint.get("fallback_latest_result"))


def _candidate_next_validation(blueprint: dict[str, Any], state: dict[str, Any], *, decision: str) -> str:
    if decision == "reject":
        return _clean_text(blueprint.get("next_validation_ready", "None."))
    if _is_data_blocked(state):
        return _clean_text(blueprint.get("next_validation_data_blocked"))
    if _is_drawdown_blocked(state):
        return _clean_text(blueprint.get("next_validation_drawdown"))
    return _clean_text(blueprint.get("next_validation_ready"))


def _candidate_artifacts(
    *,
    branch_record: dict[str, Any] | None,
    evidence_record: dict[str, Any] | None,
    paths: Any,
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
    paths: Any,
    branch_record: dict[str, Any] | None = None,
    evidence_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    project_id = _project_id_from_state(state)
    blueprint = _variant_blueprint(strategy_id, project_id=project_id)
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
        "required_data": str(blueprint.get("required_data", _crypto_required_data())),
        "current_stage": stage,
        "latest_action": _candidate_latest_action(strategy_id, state, blueprint, branch_record, evidence_record),
        "latest_result": _candidate_latest_result(strategy_id, state, blueprint, evidence_record, decision),
        "decision": decision,
        "next_validation": _candidate_next_validation(blueprint, state, decision=decision),
        "owner": owner,
        "subagents_assigned": subagents_assigned,
        "artifact_refs": _candidate_artifacts(
            branch_record=branch_record,
            evidence_record=evidence_record,
            paths=paths,
        ),
        "blocked_by": blocked_by,
        "kill_criteria": str(blueprint.get("kill_criteria", "")),
    }


def _generated_candidates(state: dict[str, Any], paths: Any) -> list[dict[str, Any]]:
    project_id = _project_id_from_state(state)
    branch_records = _latest_branch_records(paths.branch_ledger_path)
    evidence_records = _latest_evidence_records(paths.evidence_ledger_path)
    order = list(_blueprints_for_project(project_id).keys())
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


def _should_regenerate_candidates(current_candidates: list[dict[str, Any]], *, project_id: str) -> bool:
    valid_ids = set(_blueprints_for_project(project_id).keys())
    current_ids = {
        str(item.get("strategy_id", "")).strip()
        for item in current_candidates
        if isinstance(item, dict) and str(item.get("strategy_id", "")).strip()
    }
    if not current_ids:
        return True
    if project_id == CANONICAL_PROJECT_ID and not (current_ids & valid_ids):
        return True
    return False


def _normalize_candidate(candidate: dict[str, Any], *, state: dict[str, Any], paths: Any) -> dict[str, Any]:
    strategy_id = str(candidate.get("strategy_id", "")).strip() or _default_strategy_id(_project_id_from_state(state))
    generated = _candidate_from_blueprint(strategy_id=strategy_id, state=state, paths=paths)
    merged = dict(generated)
    merged.update({key: value for key, value in candidate.items() if value not in (None, "")})
    for key in [
        "track",
        "current_stage",
        "latest_action",
        "latest_result",
        "decision",
        "next_validation",
        "owner",
        "subagents_assigned",
        "artifact_refs",
        "blocked_by",
    ]:
        merged[key] = generated[key]
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
        return _dedupe_keep_order(requested_focus)[:3]
    return summary["primary_ids"][:3]


def ensure_strategy_visibility_state(state: dict[str, Any], *, paths: Any) -> dict[str, Any]:
    updated = dict(state)
    current_candidates = list(updated.get("strategy_candidates", []) or [])
    project_id = _project_id_from_state(updated)
    if current_candidates and not _should_regenerate_candidates(current_candidates, project_id=project_id):
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
    project_id = _project_id_from_state(state)
    round_type = "prerequisite_recovery" if _is_data_blocked(state) else "strategy_progress"
    blocker = _clean_text(_blocker_text(state))
    if round_type == "prerequisite_recovery":
        strategy_line = (
            f"Research is still blocked on prerequisites. Current blocker: {blocker}. "
            "Restore truthful OKX inputs before treating any strategy path as validated."
        )
        system_line = (
            "This round is about restoring the research floor, keeping the active strategy objects honest, and preventing "
            "legacy A-share assumptions from steering the current crypto program."
        )
    else:
        main_focus = primary[0]["name"] if primary else "the active mainline"
        strategy_line = f"Keep pushing {main_focus} while holding the current blocker in view: {blocker}."
        system_line = (
            "This round is allowed to move strategy work forward, but only through bounded experiments, explicit evaluation, "
            "and postmortem discipline."
        )
    return {
        "project_id": project_id,
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
        "primary_names": [f"{item['strategy_id']} ({item['name']})" for item in primary[:3]],
        "secondary_names": [f"{item['strategy_id']} ({item['name']})" for item in secondary[:3]],
        "blocked_names": [f"{item['strategy_id']} ({item['name']})" for item in blocked[:5]],
        "rejected_names": [f"{item['strategy_id']} ({item['name']})" for item in rejected[:5]],
        "promoted_names": [f"{item['strategy_id']} ({item['name']})" for item in promoted[:5]],
    }


def render_strategy_board(state: dict[str, Any], *, paths: Any) -> str:
    summary = summarize_strategy_visibility(state)
    blocker = _clean_text(_blocker_text(state))
    primary = summary.get("primary_names") or ["Not recorded."]
    secondary = summary.get("secondary_names") or ["None."]
    blocked = summary.get("blocked_names") or ["None."]
    rejected = summary.get("rejected_names") or ["None."]
    promoted = summary.get("promoted_names") or ["None."]
    lines = [
        "# Strategy Research Board",
        "",
        f"- project_id: {summary['project_id']}",
        f"- round_type: {summary['round_type']}",
        f"- blocker: {blocker}",
        f"- strategy_line: {summary['strategy_line']}",
        f"- system_line: {summary['system_line']}",
        "",
        "## Primary tracks",
        *(f"- {item}" for item in primary),
        "",
        "## Secondary tracks",
        *(f"- {item}" for item in secondary),
        "",
        "## Blocked tracks",
        *(f"- {item}" for item in blocked),
        "",
        "## Rejected tracks",
        *(f"- {item}" for item in rejected),
        "",
        "## Promoted tracks",
        *(f"- {item}" for item in promoted),
        "",
        "## Related tracked memory",
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
        f"- category: {candidate['category']}",
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
        "# Research Progress",
        "",
        f"- round_type: {summary['round_type']}",
        f"- system_line: {summary['system_line']}",
        f"- strategy_line: {summary['strategy_line']}",
        f"- primary_tracks: {', '.join(summary['primary_names']) or 'Not recorded.'}",
        f"- blocker: {_clean_text(_blocker_text(state))}",
        f"- blocked_tracks: {', '.join(summary['blocked_names']) or 'None.'}",
        f"- rejected_tracks: {', '.join(summary['rejected_names']) or 'None.'}",
        f"- next_priority_action: {_clean_text(state.get('next_priority_action'))}",
    ]
    return "\n".join(lines)


def render_strategy_cards(state: dict[str, Any], *, paths: Any) -> dict[Path, str]:
    cards: dict[Path, str] = {}
    for candidate in state.get("strategy_candidates", []) or []:
        if not isinstance(candidate, dict):
            continue
        strategy_id = str(candidate.get("strategy_id", "")).strip()
        if not strategy_id:
            continue
        cards[paths.strategy_candidates_dir / f"{strategy_id}.md"] = render_strategy_candidate_card(candidate)
    return cards
