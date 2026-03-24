from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from ..project import resolve_project_paths
from .ledger import append_jsonl, to_jsonable
from .templates import (
    DOCS_AGENTS_TEMPLATE,
    HYPOTHESIS_QUEUE_TEMPLATE,
    POSTMORTEMS_TEMPLATE,
    PROJECT_STATE_TEMPLATE,
    QUANT_AGENTS_TEMPLATE,
    ROOT_AGENTS_TEMPLATE,
    SCRIPTS_AGENTS_TEMPLATE,
    TESTS_AGENTS_TEMPLATE,
    VERIFY_LAST_TEMPLATE,
)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _write_if_missing(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return path


def _read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    path.write_text(path.read_text(encoding="utf-8").rstrip() + "\n", encoding="utf-8")
    return path


def _git_value(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def _normalize_list(values: Iterable[str] | None) -> list[str]:
    out: list[str] = []
    for value in values or []:
        text = str(value).strip()
        if text:
            out.append(text)
    return out


def _is_missing_or_empty(path: Path) -> bool:
    return not path.exists() or not path.read_text(encoding="utf-8").strip()


def _parse_bullet_state(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ") and ":" in stripped:
            key, value = stripped[2:].split(":", 1)
            data[key.strip()] = value.strip()
            current_key = key.strip()
            continue
        if stripped.startswith("- ") and current_key is None:
            data.setdefault("notes", []).append(stripped[2:].strip())
            continue
        if raw_line.startswith("  - ") and current_key:
            data.setdefault(current_key, [])
            if not isinstance(data[current_key], list):
                data[current_key] = [str(data[current_key]).strip()]
            data[current_key].append(stripped[2:].strip())
    return data


def _parse_hypotheses(text: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or not stripped[0].isdigit():
            continue
        try:
            _, remainder = stripped.split(".", 1)
        except ValueError:
            continue
        entry = remainder.strip()
        if entry.startswith("[") and "]" in entry:
            status, hypothesis = entry[1:].split("]", 1)
            items.append({"status": status.strip().lower(), "hypothesis": hypothesis.strip()})
        elif entry:
            items.append({"status": "pending", "hypothesis": entry})
    return items


def _parse_section_bullets(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    target = heading.strip().lower()
    in_section = False
    items: list[str] = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("## "):
            in_section = stripped[3:].strip().lower() == target
            continue
        if not in_section:
            continue
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def _parse_legacy_research_memory(text: str) -> dict[str, list[str]]:
    durable = _parse_section_bullets(text, "Durable Facts")
    negative = _parse_section_bullets(text, "Negative Memory")
    next_steps = _parse_section_bullets(text, "Next-Step Memory")
    if durable or negative or next_steps:
        return {
            "durable_facts": durable,
            "negative_memory": negative,
            "next_step_memory": next_steps,
        }

    data = _parse_bullet_state(text)
    return {
        "durable_facts": _normalize_list(data.get("Durable facts") or data.get("durable_facts")),
        "negative_memory": _normalize_list(data.get("Negative memory") or data.get("negative_memory")),
        "next_step_memory": _normalize_list(data.get("Next-step memory") or data.get("next_step_memory")),
    }


def _render_research_memory(state: dict[str, Any]) -> str:
    durable = _normalize_list(state.get("durable_facts"))
    negative = _normalize_list(state.get("negative_memory"))
    next_steps = _normalize_list(state.get("next_step_memory"))
    lines = ["# Research Memory", "", "## Durable Facts"]
    lines.extend([f"- {item}" for item in durable] or ["- none recorded"])
    lines.extend(["", "## Negative Memory"])
    lines.extend([f"- {item}" for item in negative] or ["- none recorded"])
    lines.extend(["", "## Next-Step Memory"])
    lines.extend([f"- {item}" for item in next_steps] or ["- none recorded"])
    return "\n".join(lines)


def _extract_last_postmortem(text: str) -> dict[str, str]:
    blocks = [block.strip() for block in text.split("\n## ") if block.strip()]
    if not blocks:
        return {}
    last = blocks[-1]
    lines = last.splitlines()
    headline = lines[0]
    payload: dict[str, str] = {
        "timestamp": headline,
        "experiment_id": headline.split("|", 1)[-1].strip() if "|" in headline else headline.strip(),
    }
    for line in lines[1:]:
        stripped = line.strip()
        if stripped.startswith("- ") and ":" in stripped:
            key, value = stripped[2:].split(":", 1)
            payload[key.strip()] = value.strip()
    return payload


def _compact_legacy_ledger_entry(project: str, raw_line: str, state: dict[str, Any]) -> dict[str, Any] | None:
    stripped = raw_line.strip()
    if not stripped:
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None

    evaluation = payload.get("evaluation", {}) if isinstance(payload, dict) else {}
    decision = evaluation.get("promotion_decision", {}) if isinstance(evaluation, dict) else {}
    metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
    plan = payload.get("plan", {}) if isinstance(payload, dict) else {}
    execution = payload.get("execution", {}) if isinstance(payload, dict) else {}
    output_refs: list[str] = []
    outputs = execution.get("outputs", {}) if isinstance(execution, dict) else {}
    if isinstance(outputs, dict):
        for value in outputs.values():
            if isinstance(value, dict):
                for item in value.values():
                    if isinstance(item, str) and (":" in item or "\\" in item or "/" in item):
                        output_refs.append(item)

    return {
        "timestamp": payload.get("timestamp", _utc_now()),
        "project": metadata.get("project", project),
        "experiment_id": payload.get("cycle_id") or payload.get("experiment_id", "legacy"),
        "hypothesis": plan.get("primary_hypothesis") or (payload.get("hypotheses") or [""])[0],
        "commit": metadata.get("commit") or state.get("head", "unknown"),
        "config_hash": metadata.get("config_hash", "unknown"),
        "result": "passed" if evaluation.get("passed") else "blocked",
        "blockers": _normalize_list(decision.get("reasons")),
        "artifact_refs": _normalize_list(output_refs),
    }


def _default_session_state(project: str, *, root: Path, paths) -> dict[str, Any]:
    return {
        "project": project,
        "current_task": "Keep the Phase 1 Research OS reproducible with tracked long-term memory and honest runtime artifacts.",
        "current_phase": "Phase 1 Research OS",
        "current_blocker": "Default project still lacks usable validated bars for the frozen universe.",
        "current_capability_boundary": "Engineering guardrails work; real default-project research remains blocked on data coverage.",
        "next_priority_action": "Restore a usable validated bar snapshot for the frozen default universe.",
        "last_verified_capability": "Contract and dry-run orchestration tests passed in the repository virtual environment.",
        "last_failed_capability": "Promotion on the default project is blocked by missing research inputs.",
        "durable_facts": [
            "The limit-up screening path now shares one audited research core between the standalone script and the modular steps.",
            "Tracked long-term memory lives under `memory/projects/<project>/`; runtime artifacts stay under `data/` and `artifacts/`.",
        ],
        "negative_memory": [
            "Default-project promotion is not trustworthy until validated bars exist for the frozen universe.",
            "Ignored runtime directories are not sufficient as the sole store for durable project memory.",
        ],
        "next_step_memory": [
            "Restore validated default-project bars before trusting any research conclusion.",
            "Keep compact tracked ledgers and handoff files in sync with runtime experiment payloads.",
        ],
        "latest_hypotheses": _parse_hypotheses(HYPOTHESIS_QUEUE_TEMPLATE),
        "last_failure": {},
        "verify_last": {
            "passed_commands": [],
            "failed_commands": [],
            "default_project_data_status": "unknown",
            "conclusion_boundary_engineering": "unknown",
            "conclusion_boundary_research": "unknown",
        },
        "tracked_memory_dir": str(paths.memory_dir),
        "runtime_meta_dir": str(paths.meta_dir),
        "runtime_artifacts_dir": str(paths.artifacts_dir),
        "head": _git_value(root, "rev-parse", "HEAD"),
        "branch": _git_value(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "last_updated": _utc_now(),
    }


def _merge_state(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if value is None:
            continue
        merged[key] = value
    return merged


def _render_project_state(state: dict[str, Any]) -> str:
    lines = [
        "# Project State",
        "",
        f"- current_total_task: {state.get('current_task', 'unknown')}",
        f"- current_phase: {state.get('current_phase', 'unknown')}",
        f"- current_blocker: {state.get('current_blocker', 'unknown')}",
        f"- current_real_capability_boundary: {state.get('current_capability_boundary', 'unknown')}",
        f"- next_priority_action: {state.get('next_priority_action', 'unknown')}",
        f"- last_verified_capability: {state.get('last_verified_capability', 'unknown')}",
        f"- last_failed_capability: {state.get('last_failed_capability', 'unknown')}",
    ]
    return "\n".join(lines)


def _render_hypothesis_queue(hypotheses: list[dict[str, str]]) -> str:
    lines = ["# Hypothesis Queue", ""]
    if not hypotheses:
        lines.append("1. [pending] No active hypothesis yet.")
        return "\n".join(lines)
    for idx, item in enumerate(hypotheses, start=1):
        lines.append(f"{idx}. [{item['status']}] {item['hypothesis']}")
    return "\n".join(lines)


def _render_verify_last(state: dict[str, Any]) -> str:
    verify = state.get("verify_last", {}) or {}
    passed = _normalize_list(verify.get("passed_commands"))
    failed = _normalize_list(verify.get("failed_commands"))
    lines = [
        "# Verify Last",
        "",
        f"- head: {state.get('head', 'unknown')}",
        f"- branch: {state.get('branch', 'unknown')}",
        "- passed_commands:",
    ]
    lines.extend([f"  - {item}" for item in passed] or ["  - none recorded"])
    lines.append("- failed_commands:")
    lines.extend([f"  - {item}" for item in failed] or ["  - none recorded"])
    lines.extend(
        [
            f"- default_project_data_status: {verify.get('default_project_data_status', 'unknown')}",
            f"- conclusion_boundary_engineering: {verify.get('conclusion_boundary_engineering', 'unknown')}",
            f"- conclusion_boundary_research: {verify.get('conclusion_boundary_research', 'unknown')}",
        ],
    )
    return "\n".join(lines)


def _render_handoff(state: dict[str, Any], paths) -> str:
    failure = state.get("last_failure", {}) or {}
    lines = [
        "# Handoff Next Chat",
        "",
        "## Current Total Task",
        state.get("current_task", "unknown"),
        "",
        "## Current Phase",
        state.get("current_phase", "unknown"),
        "",
        "## Completed",
        f"- Tracked memory dir: {paths.memory_dir}",
        f"- Runtime meta dir: {paths.meta_dir}",
        f"- Runtime artifacts dir: {paths.artifacts_dir}",
        "",
        "## Current Blocker",
        state.get("current_blocker", "unknown"),
        "",
        "## Recent Critical Failure",
        failure.get("summary", state.get("last_failed_capability", "none recorded")),
        "",
        "## Current Real Capability Boundary",
        state.get("current_capability_boundary", "unknown"),
        "",
        "## Next Highest-Priority Action",
        state.get("next_priority_action", "unknown"),
        "",
        "## Read First In The Next Chat",
        f"- {paths.project_state_path}",
        f"- {paths.verify_last_path}",
        f"- {paths.migration_prompt_path}",
        f"- {paths.research_memory_path}",
    ]
    return "\n".join(lines)


def _render_migration_prompt(state: dict[str, Any], paths) -> str:
    failure = state.get("last_failure", {}) or {}
    verify = state.get("verify_last", {}) or {}
    lines = [
        "# Migration Prompt Next Chat",
        "",
        "## Current Total Task",
        state.get("current_task", "unknown"),
        "",
        "## Current Phase",
        state.get("current_phase", "unknown"),
        "",
        "## Current Repo / Branch / HEAD",
        f"- repo_root: {paths.root}",
        f"- branch: {state.get('branch', 'unknown')}",
        f"- head: {state.get('head', 'unknown')}",
        "",
        "## Confirmed Facts",
        f"- tracked_memory_dir: {paths.memory_dir}",
        f"- runtime_meta_dir: {paths.meta_dir}",
        f"- runtime_artifacts_dir: {paths.artifacts_dir}",
        f"- current_blocker: {state.get('current_blocker', 'unknown')}",
        "",
        "## Unconfirmed Questions",
        "- No additional unconfirmed questions have been recorded yet.",
        "",
        "## Recent Critical Failure",
        failure.get("summary", state.get("last_failed_capability", "none recorded")),
        "",
        "## Current Blocker",
        state.get("current_blocker", "unknown"),
        "",
        "## Next Highest-Priority Action",
        state.get("next_priority_action", "unknown"),
        "",
        "## Avoid Repeating Work",
        "- Do not move durable memory back into ignored runtime directories.",
        "- Do not trust default-project research claims until validated bars exist for the frozen universe.",
        "",
        "## Required Verification First",
    ]
    lines.extend([f"- {item}" for item in _normalize_list(verify.get("passed_commands"))] or ["- Run the tracked-memory and contract test suite first."])
    lines.extend(
        [
            "",
            "## Read These Files First If Context Is Thin",
            f"- {paths.project_state_path}",
            f"- {paths.verify_last_path}",
            f"- {paths.handoff_path}",
            f"- {paths.research_memory_path}",
            f"- {paths.postmortems_path}",
            "",
            "## Tracked Memory Location",
            str(paths.memory_dir),
            "",
            "## Runtime Artifacts Location",
            f"- {paths.meta_dir}",
            f"- {paths.artifacts_dir}",
            "",
            "## Current Real Capability Boundary",
            state.get("current_capability_boundary", "unknown"),
        ],
    )
    return "\n".join(lines)


def _bootstrap_repo_files(root: Path) -> None:
    _write_if_missing(root / "AGENTS.md", ROOT_AGENTS_TEMPLATE)
    _write_if_missing(root / "quant_mvp" / "AGENTS.md", QUANT_AGENTS_TEMPLATE)
    _write_if_missing(root / "scripts" / "AGENTS.md", SCRIPTS_AGENTS_TEMPLATE)
    _write_if_missing(root / "tests" / "AGENTS.md", TESTS_AGENTS_TEMPLATE)
    _write_if_missing(root / "docs" / "AGENTS.md", DOCS_AGENTS_TEMPLATE)


def _legacy_memory_paths(paths) -> dict[str, Path]:
    return {
        "project_state": paths.meta_dir / "PROJECT_STATE.md",
        "research_memory": paths.meta_dir / "RESEARCH_MEMORY.md",
        "postmortems": paths.meta_dir / "POSTMORTEMS.md",
        "hypothesis_queue": paths.meta_dir / "HYPOTHESIS_QUEUE.md",
        "experiment_ledger": paths.meta_dir / "EXPERIMENT_LEDGER.jsonl",
    }


def _migrate_legacy_memory(paths, state: dict[str, Any]) -> dict[str, Any]:
    legacy = _legacy_memory_paths(paths)
    if _is_missing_or_empty(paths.project_state_path) and legacy["project_state"].exists():
        _write_text(paths.project_state_path, legacy["project_state"].read_text(encoding="utf-8"))
    if _is_missing_or_empty(paths.postmortems_path) and legacy["postmortems"].exists():
        _write_text(paths.postmortems_path, legacy["postmortems"].read_text(encoding="utf-8"))
    if _is_missing_or_empty(paths.hypothesis_queue_path) and legacy["hypothesis_queue"].exists():
        _write_text(paths.hypothesis_queue_path, legacy["hypothesis_queue"].read_text(encoding="utf-8"))

    if _is_missing_or_empty(paths.experiment_ledger_path) and legacy["experiment_ledger"].exists():
        compact_entries = [
            item
            for item in (
                _compact_legacy_ledger_entry(paths.project, line, state)
                for line in legacy["experiment_ledger"].read_text(encoding="utf-8").splitlines()
            )
            if item is not None
        ]
        if compact_entries:
            paths.experiment_ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with open(paths.experiment_ledger_path, "w", encoding="utf-8") as handle:
                for item in compact_entries:
                    handle.write(json.dumps(to_jsonable(item), ensure_ascii=False, sort_keys=True))
                    handle.write("\n")

    project_state_text = _read_text(paths.project_state_path) or _read_text(legacy["project_state"])
    parsed_state = _parse_bullet_state(project_state_text)
    if parsed_state:
        state = _merge_state(
            state,
            {
                "current_phase": parsed_state.get("phase") or parsed_state.get("current_phase"),
                "current_blocker": parsed_state.get("data_status") or parsed_state.get("current_blocker"),
                "current_capability_boundary": parsed_state.get("data_status") or state.get("current_capability_boundary"),
                "next_priority_action": (
                    parsed_state.get("next_priority", [state.get("next_priority_action")])[0]
                    if isinstance(parsed_state.get("next_priority"), list)
                    else parsed_state.get("next_priority_action") or state.get("next_priority_action")
                ),
                "last_failed_capability": parsed_state.get("last_agent_cycle") or state.get("last_failed_capability"),
            },
        )

    research_memory_text = _read_text(legacy["research_memory"]) or _read_text(paths.research_memory_path)
    research_memory = _parse_legacy_research_memory(research_memory_text)
    if research_memory["durable_facts"]:
        state["durable_facts"] = research_memory["durable_facts"]
    if research_memory["negative_memory"]:
        state["negative_memory"] = research_memory["negative_memory"]
    if research_memory["next_step_memory"]:
        state["next_step_memory"] = research_memory["next_step_memory"]

    hypotheses_text = _read_text(paths.hypothesis_queue_path) or _read_text(legacy["hypothesis_queue"])
    hypotheses = _parse_hypotheses(hypotheses_text)
    if hypotheses:
        state["latest_hypotheses"] = hypotheses

    postmortem_text = _read_text(paths.postmortems_path) or _read_text(legacy["postmortems"])
    last_failure = _extract_last_postmortem(postmortem_text)
    if last_failure:
        state["last_failure"] = {
            "timestamp": last_failure.get("timestamp", ""),
            "experiment_id": last_failure.get("experiment_id", ""),
            "summary": last_failure.get("summary", ""),
            "root_cause": last_failure.get("root_cause", ""),
            "corrective_action": last_failure.get("corrective_action", ""),
            "resolution_status": last_failure.get("resolution_status", "not_fixed"),
        }
        state["last_failed_capability"] = last_failure.get("summary", state.get("last_failed_capability"))
        if last_failure.get("root_cause"):
            state["current_blocker"] = last_failure.get("root_cause")
    return state


def _refresh_derived_memory(paths, state: dict[str, Any]) -> None:
    state = dict(state)
    state["head"] = _git_value(paths.root, "rev-parse", "HEAD")
    state["branch"] = _git_value(paths.root, "rev-parse", "--abbrev-ref", "HEAD")
    state["tracked_memory_dir"] = str(paths.memory_dir)
    state["runtime_meta_dir"] = str(paths.meta_dir)
    state["runtime_artifacts_dir"] = str(paths.artifacts_dir)
    state["last_updated"] = _utc_now()
    _write_text(paths.project_state_path, _render_project_state(state))
    _write_text(paths.research_memory_path, _render_research_memory(state))
    _write_text(paths.hypothesis_queue_path, _render_hypothesis_queue(state.get("latest_hypotheses", [])))
    _write_text(paths.verify_last_path, _render_verify_last(state))
    _write_text(paths.handoff_path, _render_handoff(state, paths))
    _write_text(paths.migration_prompt_path, _render_migration_prompt(state, paths))
    _write_json(paths.session_state_path, state)


def bootstrap_memory_files(project: str, *, repo_root: Path | None = None) -> dict[str, Path]:
    paths = resolve_project_paths(project, root=repo_root)
    paths.ensure_dirs()
    _bootstrap_repo_files(paths.root)

    tracked_files = {
        "project_state": paths.project_state_path,
        "research_memory": paths.research_memory_path,
        "postmortems": paths.postmortems_path,
        "hypothesis_queue": paths.hypothesis_queue_path,
        "experiment_ledger": paths.experiment_ledger_path,
        "handoff_next_chat": paths.handoff_path,
        "migration_prompt_next_chat": paths.migration_prompt_path,
        "verify_last": paths.verify_last_path,
        "session_state": paths.session_state_path,
        "memory_dir": paths.memory_dir,
        "runtime_meta_dir": paths.meta_dir,
        "runtime_cycles_dir": paths.runtime_cycles_dir,
    }

    state = _read_json(paths.session_state_path, default=_default_session_state(project, root=paths.root, paths=paths))
    state = _migrate_legacy_memory(paths, state)
    _write_if_missing(paths.project_state_path, PROJECT_STATE_TEMPLATE)
    _write_if_missing(paths.postmortems_path, POSTMORTEMS_TEMPLATE)
    _write_if_missing(paths.hypothesis_queue_path, HYPOTHESIS_QUEUE_TEMPLATE)
    _write_if_missing(paths.verify_last_path, VERIFY_LAST_TEMPLATE)
    if not paths.experiment_ledger_path.exists():
        paths.experiment_ledger_path.write_text("", encoding="utf-8")
    _refresh_derived_memory(paths, state)
    return tracked_files


def _load_state(project: str, *, repo_root: Path | None = None) -> tuple[Any, dict[str, Any]]:
    files = bootstrap_memory_files(project, repo_root=repo_root)
    paths = resolve_project_paths(project, root=repo_root)
    state = _read_json(paths.session_state_path, default=_default_session_state(project, root=paths.root, paths=paths))
    return paths, state


def sync_project_state(project: str, summary: dict[str, Any], *, repo_root: Path | None = None) -> Path:
    paths, state = _load_state(project, repo_root=repo_root)
    state = _merge_state(
        state,
        {
            "current_task": summary.get("current_task") or summary.get("current_total_task") or state.get("current_task"),
            "current_phase": summary.get("current_phase") or summary.get("phase") or state.get("current_phase"),
            "current_blocker": summary.get("current_blocker") or state.get("current_blocker"),
            "current_capability_boundary": (
                summary.get("current_capability_boundary")
                or summary.get("current_real_capability_boundary")
                or state.get("current_capability_boundary")
            ),
            "next_priority_action": summary.get("next_priority_action") or state.get("next_priority_action"),
            "last_verified_capability": summary.get("last_verified_capability") or state.get("last_verified_capability"),
            "last_failed_capability": summary.get("last_failed_capability") or state.get("last_failed_capability"),
        },
    )
    _refresh_derived_memory(paths, state)
    return paths.project_state_path


def sync_research_memory(
    project: str,
    *,
    durable_facts: list[str] | None = None,
    negative_memory: list[str] | None = None,
    next_step_memory: list[str] | None = None,
    repo_root: Path | None = None,
) -> Path:
    paths, state = _load_state(project, repo_root=repo_root)
    if durable_facts is None and negative_memory is None and next_step_memory is None:
        return paths.research_memory_path
    if durable_facts is not None:
        state["durable_facts"] = _normalize_list(durable_facts)
    if negative_memory is not None:
        state["negative_memory"] = _normalize_list(negative_memory)
    if next_step_memory is not None:
        state["next_step_memory"] = _normalize_list(next_step_memory)
    _refresh_derived_memory(paths, state)
    return paths.research_memory_path


def update_hypothesis_queue(
    project: str,
    hypotheses: list[str] | list[dict[str, str]],
    *,
    repo_root: Path | None = None,
) -> Path:
    paths, state = _load_state(project, repo_root=repo_root)
    normalized: list[dict[str, str]] = []
    for item in hypotheses:
        if isinstance(item, dict):
            hypothesis = str(item.get("hypothesis", "")).strip()
            status = str(item.get("status", "pending")).strip().lower() or "pending"
        else:
            hypothesis = str(item).strip()
            status = "pending"
        if hypothesis:
            normalized.append({"status": status, "hypothesis": hypothesis})
    state["latest_hypotheses"] = normalized
    _refresh_derived_memory(paths, state)
    return paths.hypothesis_queue_path


def record_experiment_result(project: str, entry: dict[str, Any], *, repo_root: Path | None = None) -> Path:
    paths, state = _load_state(project, repo_root=repo_root)
    compact = {
        "timestamp": entry.get("timestamp", _utc_now()),
        "project": project,
        "experiment_id": entry.get("experiment_id", "unknown"),
        "hypothesis": entry.get("hypothesis", ""),
        "commit": entry.get("commit") or state.get("head", "unknown"),
        "config_hash": entry.get("config_hash", "unknown"),
        "result": entry.get("result", "unknown"),
        "blockers": _normalize_list(entry.get("blockers")),
        "artifact_refs": _normalize_list(entry.get("artifact_refs")),
    }
    append_jsonl(paths.experiment_ledger_path, compact)
    return paths.experiment_ledger_path


def record_failure(
    project: str,
    entry: dict[str, Any],
    *,
    repo_root: Path | None = None,
    append_ledger: bool = False,
    ledger_entry: dict[str, Any] | None = None,
) -> Path:
    paths, state = _load_state(project, repo_root=repo_root)
    payload = {
        "timestamp": str(entry.get("timestamp", _utc_now())),
        "experiment_id": str(entry.get("experiment_id", "unknown")),
        "summary": str(entry.get("summary", "")).strip(),
        "root_cause": str(entry.get("root_cause", "")).strip(),
        "corrective_action": str(entry.get("corrective_action", "")).strip(),
        "resolution_status": str(entry.get("resolution_status", "not_fixed")).strip(),
    }
    existing = _read_text(paths.postmortems_path)
    block = [
        "",
        f"## {payload['timestamp']} | {payload['experiment_id']}",
        f"- summary: {payload['summary']}",
        f"- root_cause: {payload['root_cause']}",
        f"- corrective_action: {payload['corrective_action']}",
        f"- resolution_status: {payload['resolution_status']}",
    ]
    _write_text(paths.postmortems_path, (existing + "\n" + "\n".join(block)).strip())
    state["last_failure"] = payload
    state["last_failed_capability"] = payload["summary"] or state.get("last_failed_capability")
    if payload["root_cause"]:
        state["current_blocker"] = payload["root_cause"]
    _refresh_derived_memory(paths, state)
    if append_ledger:
        record_experiment_result(
            project,
            ledger_entry
            or {
                "timestamp": payload["timestamp"],
                "experiment_id": payload["experiment_id"],
                "result": "failed",
                "blockers": [payload["root_cause"]],
            },
            repo_root=repo_root,
        )
    return paths.postmortems_path


def record_agent_cycle(project: str, payload: dict[str, Any], *, repo_root: Path | None = None) -> dict[str, Path]:
    paths, state = _load_state(project, repo_root=repo_root)
    timestamp = str(payload.get("timestamp") or _utc_now())
    cycle_id = str(payload.get("cycle_id", "cycle"))
    jsonable = to_jsonable(payload)
    paths.runtime_cycles_dir.mkdir(parents=True, exist_ok=True)
    cycle_path = paths.runtime_cycles_dir / f"{timestamp.replace(':', '').replace('-', '')}_{cycle_id}.json"
    cycle_path.write_text(json.dumps(jsonable, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    cycle_path.write_text(cycle_path.read_text(encoding="utf-8").rstrip() + "\n", encoding="utf-8")

    decision = jsonable.get("evaluation", {}).get("promotion_decision", {}) if isinstance(jsonable, dict) else {}
    blockers = decision.get("reasons", []) if isinstance(decision, dict) else []
    result = "passed" if jsonable.get("evaluation", {}).get("passed") else "blocked"
    record_experiment_result(
        project,
        {
            "timestamp": timestamp,
            "experiment_id": cycle_id,
            "hypothesis": jsonable.get("plan", {}).get("primary_hypothesis", ""),
            "config_hash": jsonable.get("metadata", {}).get("config_hash", "unknown"),
            "result": result,
            "blockers": blockers,
            "artifact_refs": [str(cycle_path)],
        },
        repo_root=repo_root,
    )
    _refresh_derived_memory(paths, state)
    return {
        "cycle_path": cycle_path,
        "ledger_path": paths.experiment_ledger_path,
    }


def write_verify_snapshot(project: str, summary: dict[str, Any], *, repo_root: Path | None = None) -> Path:
    paths, state = _load_state(project, repo_root=repo_root)
    verify = dict(state.get("verify_last", {}))
    verify.update(
        {
            "passed_commands": _normalize_list(summary.get("passed_commands")),
            "failed_commands": _normalize_list(summary.get("failed_commands")),
            "default_project_data_status": summary.get("default_project_data_status", verify.get("default_project_data_status", "unknown")),
            "conclusion_boundary_engineering": summary.get(
                "conclusion_boundary_engineering",
                verify.get("conclusion_boundary_engineering", "unknown"),
            ),
            "conclusion_boundary_research": summary.get(
                "conclusion_boundary_research",
                verify.get("conclusion_boundary_research", "unknown"),
            ),
        },
    )
    state["verify_last"] = verify
    state["last_verified_capability"] = summary.get("last_verified_capability") or state.get("last_verified_capability")
    _refresh_derived_memory(paths, state)
    return paths.verify_last_path


def generate_handoff(project: str, *, repo_root: Path | None = None) -> dict[str, Path]:
    paths, state = _load_state(project, repo_root=repo_root)
    _refresh_derived_memory(paths, state)
    return {
        "handoff_next_chat": paths.handoff_path,
        "migration_prompt_next_chat": paths.migration_prompt_path,
        "session_state": paths.session_state_path,
    }
