from __future__ import annotations

from pathlib import Path
from typing import Any

from .subagent_models import SubagentRoleTemplate


def default_subagent_state(paths) -> dict[str, Any]:
    return {
        "subagent_gate_mode": "AUTO",
        "subagent_continue_recommended": False,
        "subagent_continue_reason": "The default-project data blocker should be cleared before expanding into multiple subagents.",
        "subagent_plan": {
            "gate_mode": "AUTO",
            "recommended_gate": "OFF",
            "recommended_count": 0,
            "recommended_roles": [],
            "work_packages": [],
            "should_expand": False,
            "no_split_reason": "The current default-project blocker does not justify extra coordination yet.",
            "rationale": "Stay effectively OFF until validated bars restore independent work packages.",
            "score": 0.0,
        },
        "subagent_last_event": {},
        "subagents": [],
    }


def summarize_subagent_state(state: dict[str, Any]) -> dict[str, Any]:
    records = list(state.get("subagents", []))
    active = [item["subagent_id"] for item in records if item.get("status") == "active"]
    blocked = [item["subagent_id"] for item in records if item.get("status") == "blocked"]
    retired = [item["subagent_id"] for item in records if item.get("status") in {"retired", "merged", "archived", "canceled"}]
    transient = [item["subagent_id"] for item in records if item.get("transient", True)]
    templates = [item["subagent_id"] for item in records if not item.get("transient", True)]
    plan = state.get("subagent_plan", {}) or {}
    last_event = state.get("subagent_last_event", {}) or {}
    return {
        "gate_mode": state.get("subagent_gate_mode", "AUTO"),
        "recommended_gate": plan.get("recommended_gate", "OFF"),
        "should_expand": bool(state.get("subagent_continue_recommended", False)),
        "continue_reason": state.get("subagent_continue_reason", "unknown"),
        "active_ids": active,
        "blocked_ids": blocked,
        "retired_ids": retired,
        "temporary_ids": transient,
        "template_ids": templates,
        "last_event": last_event,
    }


def render_subagent_registry(
    state: dict[str, Any],
    *,
    role_templates: dict[str, SubagentRoleTemplate],
) -> str:
    summary = summarize_subagent_state(state)
    plan = state.get("subagent_plan", {}) or {}
    lines = [
        "# Subagent Registry",
        "",
        "## Governance",
        f"- gate_mode: {summary['gate_mode']}",
        f"- recommended_gate: {summary['recommended_gate']}",
        f"- continue_using_subagents: {'yes' if summary['should_expand'] else 'no'}",
        f"- continue_reason: {summary['continue_reason']}",
        f"- recent_event: {summary['last_event'].get('action', 'none recorded')}",
        "",
        "## Current Sets",
        f"- active: {', '.join(summary['active_ids']) if summary['active_ids'] else 'none'}",
        f"- blocked: {', '.join(summary['blocked_ids']) if summary['blocked_ids'] else 'none'}",
        f"- retired_or_merged: {', '.join(summary['retired_ids']) if summary['retired_ids'] else 'none'}",
        f"- temporary: {', '.join(summary['temporary_ids']) if summary['temporary_ids'] else 'none'}",
        f"- long_lived_templates: {', '.join(summary['template_ids']) if summary['template_ids'] else 'none'}",
        "",
        "## Latest Plan",
        f"- recommended_count: {plan.get('recommended_count', 0)}",
        f"- recommended_roles: {', '.join(plan.get('recommended_roles', [])) or 'none'}",
        f"- no_split_reason: {plan.get('no_split_reason', '') or 'n/a'}",
        f"- rationale: {plan.get('rationale', 'n/a')}",
        "",
        "## Role Templates",
    ]
    for role, template in role_templates.items():
        lines.append(f"- {role}: {template.responsibilities[0] if template.responsibilities else 'no summary'}")
    lines.extend(["", "## Records"])
    records = list(state.get("subagents", []))
    if not records:
        lines.append("- no instantiated subagents")
        return "\n".join(lines)
    for record in records:
        lines.extend(
            [
                f"### {record['subagent_id']} | {record['role']} | {record['status']}",
                f"- summary: {record.get('summary', '')}",
                f"- transient: {record.get('transient', True)}",
                f"- allowed_paths: {', '.join(record.get('allowed_paths', [])) or 'none'}",
                f"- expected_artifacts: {', '.join(record.get('expected_artifacts', [])) or 'none'}",
                f"- artifact_dir: {record.get('artifact_dir') or 'n/a'}",
                f"- lineage: parents={', '.join(record.get('parent_ids', [])) or 'none'}; children={', '.join(record.get('child_ids', [])) or 'none'}; merged_into={record.get('merged_into') or 'n/a'}",
            ],
        )
    return "\n".join(lines)


def ensure_subagent_runtime_dir(paths, subagent_id: str) -> Path:
    path = paths.subagent_artifacts_dir / subagent_id
    path.mkdir(parents=True, exist_ok=True)
    return path
