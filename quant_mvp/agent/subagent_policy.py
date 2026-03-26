from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .subagent_models import GateMode, SubagentPlan, SubagentRoleTemplate, SubagentTaskProfile, SubagentWorkPackage


DEFAULT_POLICY = {
    "default_gate": "AUTO",
    "soft_limit": 2,
    "stretch_limit": 4,
    "hard_limit": 6,
    "min_breadth_for_split": 2,
    "min_independence_for_split": 0.65,
    "max_file_overlap_for_split": 0.4,
    "min_score_for_auto": 1.8,
    "min_score_for_stretch": 2.45,
    "weights": {
        "breadth": 0.7,
        "independence": 0.8,
        "validation_load": 0.7,
        "risk_isolation": 0.5,
        "file_overlap_penalty": 0.9,
        "coordination_penalty": 0.8,
    },
}


def _load_json_yaml(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_subagent_policy(path: Path) -> dict[str, Any]:
    payload = dict(DEFAULT_POLICY)
    loaded = _load_json_yaml(path, default=DEFAULT_POLICY)
    payload.update({key: value for key, value in loaded.items() if key != "weights"})
    payload["weights"] = dict(DEFAULT_POLICY["weights"])
    payload["weights"].update(loaded.get("weights", {}))
    return payload


def load_subagent_roles(path: Path) -> dict[str, SubagentRoleTemplate]:
    loaded = _load_json_yaml(path, default={})
    templates: dict[str, SubagentRoleTemplate] = {}
    for role, payload in loaded.items():
        templates[role] = SubagentRoleTemplate(
            role=role,
            responsibilities=list(payload.get("responsibilities", [])),
            allowed_paths=list(payload.get("allowed_paths", [])),
            expected_artifacts=list(payload.get("expected_artifacts", [])),
        )
    return templates


def _score_profile(profile: SubagentTaskProfile, policy: dict[str, Any]) -> float:
    weights = policy["weights"]
    breadth_score = min(float(profile.breadth) / 3.0, 1.0)
    return round(
        weights["breadth"] * breadth_score
        + weights["independence"] * float(profile.independence)
        + weights["validation_load"] * float(profile.validation_load)
        + weights["risk_isolation"] * float(profile.risk_isolation)
        - weights["file_overlap_penalty"] * float(profile.file_overlap)
        - weights["coordination_penalty"] * float(profile.coordination_cost),
        4,
    )


def _keyword_roles(task_summary: str, focus_tags: list[str], templates: dict[str, SubagentRoleTemplate]) -> list[str]:
    text = f"{task_summary} {' '.join(focus_tags)}".lower()
    role_candidates: list[str] = []
    if any(token in text for token in ["data", "provider", "bars", "coverage", "calendar"]):
        role_candidates.append("data_steward")
    if any(token in text for token in ["audit", "strategy", "spec", "entrypoint", "selection", "ranking"]):
        role_candidates.append("strategy_auditor")
    if any(token in text for token in ["validation", "leakage", "promotion", "baseline", "robust", "test"]):
        role_candidates.append("validation_guard")
    if any(token in text for token in ["memory", "handoff", "prompt", "session", "registry"]):
        role_candidates.append("memory_curator")
    if any(token in text for token in ["tool", "dependency", "policy", "config", "allowlist"]):
        role_candidates.append("tooling_scout")
    if any(token in text for token in ["merge", "integrate", "handoff", "cleanup", "retire"]):
        role_candidates.append("integration_merger")
    return [role for role in role_candidates if role in templates]


def _build_work_packages(
    roles: list[str],
    task_summary: str,
    templates: dict[str, SubagentRoleTemplate],
) -> list[SubagentWorkPackage]:
    packages: list[SubagentWorkPackage] = []
    for role in roles:
        template = templates[role]
        packages.append(
            SubagentWorkPackage(
                role=role,
                summary=f"{role}: {task_summary}",
                allowed_paths=template.allowed_paths,
                expected_artifacts=template.expected_artifacts,
                transient=role != "memory_curator",
            ),
        )
    return packages


def evaluate_subagent_plan(
    profile: SubagentTaskProfile,
    *,
    gate_mode: GateMode,
    policy: dict[str, Any],
    role_templates: dict[str, SubagentRoleTemplate],
) -> SubagentPlan:
    if gate_mode == "OFF":
        return SubagentPlan(
            gate_mode=gate_mode,
            recommended_gate="OFF",
            recommended_count=0,
            recommended_roles=[],
            work_packages=[],
            should_expand=False,
            no_split_reason="Gate is explicitly OFF.",
            rationale="Subagent decomposition is disabled for this task.",
            score=0.0,
        )

    score = _score_profile(profile, policy)
    breadth_ok = int(profile.breadth) >= int(policy["min_breadth_for_split"])
    independence_ok = float(profile.independence) >= float(policy["min_independence_for_split"])
    overlap_ok = float(profile.file_overlap) <= float(policy["max_file_overlap_for_split"])
    score_ok = float(score) >= float(policy["min_score_for_auto"])

    if gate_mode == "AUTO" and not breadth_ok:
        return SubagentPlan(
            gate_mode=gate_mode,
            recommended_gate="OFF",
            recommended_count=0,
            recommended_roles=[],
            work_packages=[],
            should_expand=False,
            no_split_reason="Task breadth is below the minimum threshold for safe decomposition.",
            rationale="The work is still narrow enough for one integrating agent.",
            score=score,
        )
    if gate_mode == "AUTO" and not independence_ok:
        return SubagentPlan(
            gate_mode=gate_mode,
            recommended_gate="OFF",
            recommended_count=0,
            recommended_roles=[],
            work_packages=[],
            should_expand=False,
            no_split_reason="Subtasks are too coupled to split cleanly.",
            rationale="High coupling would turn subagents into coordination overhead.",
            score=score,
        )
    if gate_mode == "AUTO" and not overlap_ok:
        return SubagentPlan(
            gate_mode=gate_mode,
            recommended_gate="OFF",
            recommended_count=0,
            recommended_roles=[],
            work_packages=[],
            should_expand=False,
            no_split_reason="File overlap is too high for efficient parallel work.",
            rationale="The same hot files would need frequent merges, so splitting is suppressed.",
            score=score,
        )
    if gate_mode == "AUTO" and not score_ok:
        return SubagentPlan(
            gate_mode=gate_mode,
            recommended_gate="OFF",
            recommended_count=0,
            recommended_roles=[],
            work_packages=[],
            should_expand=False,
            no_split_reason="The coordination-adjusted score is too low.",
            rationale="Validation and isolation benefits do not yet offset decomposition cost.",
            score=score,
        )

    candidate_roles = _keyword_roles(profile.task_summary, profile.focus_tags, role_templates)
    if not candidate_roles:
        candidate_roles = ["integration_merger"]
    soft_limit = int(policy.get("soft_limit", 2))
    stretch_limit = int(policy.get("stretch_limit", max(soft_limit, 4)))
    hard_limit = int(policy.get("hard_limit", max(stretch_limit, 6)))
    target_limit = soft_limit
    if float(score) >= float(policy.get("min_score_for_stretch", policy["min_score_for_auto"])) and int(profile.breadth) >= 4:
        target_limit = stretch_limit
    if gate_mode == "FORCE":
        target_limit = max(target_limit, min(stretch_limit, hard_limit))
    recommended_count = min(max(2, len(candidate_roles)), target_limit, hard_limit)
    recommended_roles = candidate_roles[:recommended_count]
    work_packages = _build_work_packages(recommended_roles, profile.task_summary, role_templates)
    recommended_gate: GateMode = "FORCE" if gate_mode == "FORCE" else "AUTO"
    rationale = "Independent work packages exist and the coordination-adjusted score justifies controlled decomposition."
    return SubagentPlan(
        gate_mode=gate_mode,
        recommended_gate=recommended_gate,
        recommended_count=len(work_packages),
        recommended_roles=recommended_roles,
        work_packages=work_packages,
        should_expand=True,
        no_split_reason="",
        rationale=rationale,
        score=score,
    )
