from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from ..agent.subagent_policy import load_subagent_roles
from ..agent.subagent_registry import default_subagent_state, render_subagent_registry, summarize_subagent_state
from ..project import resolve_project_paths
from .ledger import append_jsonl, to_jsonable
from .localization import humanize_text, zh_bool, zh_status, zh_stop_reason
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
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return dict(default or {})
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return dict(default or {})


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2, sort_keys=True).rstrip() + "\n"
    path.write_text(text, encoding="utf-8")
    return path


def _git_value(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def _subagent_roles_path(root: Path) -> Path:
    return root / "configs" / "subagent_roles.yaml"


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
    status_map = {
        "blocked": "blocked",
        "pending": "pending",
        "active": "active",
        "done": "done",
        "阻塞": "blocked",
        "待处理": "pending",
        "待验证": "pending",
        "进行中": "active",
        "已完成": "done",
    }
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
            key = status.strip().lower()
            items.append({"status": status_map.get(key, status_map.get(status.strip(), "pending")), "hypothesis": hypothesis.strip()})
        elif entry:
            items.append({"status": "pending", "hypothesis": entry})
    return items


def _parse_section_bullets(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    aliases = {
        "durable facts": {"durable facts", "长期事实"},
        "negative memory": {"negative memory", "负面记忆"},
        "next-step memory": {"next-step memory", "下一步记忆"},
    }
    target = aliases.get(heading.strip().lower(), {heading.strip().lower()})
    in_section = False
    items: list[str] = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("## "):
            in_section = stripped[3:].strip().lower() in target
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
        "durable_facts": _normalize_list(data.get("Durable facts") or data.get("durable_facts") or data.get("长期事实")),
        "negative_memory": _normalize_list(data.get("Negative memory") or data.get("negative_memory") or data.get("负面记忆")),
        "next_step_memory": _normalize_list(data.get("Next-step memory") or data.get("next_step_memory") or data.get("下一步记忆")),
    }


def _render_research_memory(state: dict[str, Any]) -> str:
    durable = _normalize_list(state.get("durable_facts"))
    negative = _normalize_list(state.get("negative_memory"))
    next_steps = _normalize_list(state.get("next_step_memory"))
    lines = ["# 研究记忆", "", "## 长期事实"]
    lines.extend([f"- {humanize_text(item)}" for item in durable] or ["- 未记录"])
    lines.extend(["", "## 负面记忆"])
    lines.extend([f"- {humanize_text(item)}" for item in negative] or ["- 未记录"])
    lines.extend(["", "## 下一步记忆"])
    lines.extend([f"- {humanize_text(item)}" for item in next_steps] or ["- 未记录"])
    return "\n".join(lines)


def _iterative_loop_state(state: dict[str, Any]) -> dict[str, Any]:
    payload = dict(_default_iterative_loop_state())
    payload.update(state.get("iterative_loop", {}) or {})
    payload["subagents_used"] = _normalize_list(payload.get("subagents_used"))
    payload["blocker_history"] = dict(payload.get("blocker_history", {}) or {})
    return payload


def _render_loop_summary_lines(state: dict[str, Any]) -> list[str]:
    loop = _iterative_loop_state(state)
    return [
        f"- iteration_count: {loop.get('iteration_count', 0)}",
        f"- target_iterations: {loop.get('target_iterations', 0)}",
        f"- max_iterations: {loop.get('max_iterations', 0)}",
        f"- stop_reason: {zh_stop_reason(str(loop.get('stop_reason', 'unknown')))}",
        f"- direction_change: {zh_bool(loop.get('direction_change', False))}",
        f"- blocker_escalation: {zh_bool(loop.get('blocker_escalation', False))}",
        f"- blocker_key: {loop.get('blocker_key', 'unknown')} (repeat_count={loop.get('blocker_repeat_count', 0)}, historical_count={loop.get('historical_blocker_count', 0)})",
        f"- last_classification: {humanize_text(loop.get('last_classification', 'unknown'))}",
        f"- max_active_subagents: {loop.get('max_active_subagents', 0)}",
        (
            f"- subagent_gate_mode: {loop.get('subagent_gate_mode', 'AUTO')} "
            f"(blocked/retired/merged/archived={loop.get('blocked_subagent_count', 0)}/"
            f"{loop.get('retired_subagent_count', 0)}/{loop.get('merged_subagent_count', 0)}/{loop.get('archived_subagent_count', 0)})"
        ),
        f"- subagents_used: {', '.join(loop.get('subagents_used', [])) or 'none'}",
        f"- subagent_reason: {humanize_text(loop.get('subagent_reason', 'n/a'))}",
        f"- auto_closed_subagents: {', '.join(loop.get('auto_closed_subagents', [])) or 'none'}",
        f"- alternative_subagents: {', '.join(loop.get('alternative_subagents', [])) or 'none'}",
        f"- 本轮完成: {humanize_text(loop.get('last_completed', 'none recorded'))}",
        f"- 本轮未完成: {humanize_text(loop.get('last_not_done', 'none recorded'))}",
        f"- 下一步建议: {humanize_text(loop.get('next_recommendation', 'none recorded'))}",
    ]


def _localize_postmortems_text(text: str) -> str:
    if not text.strip():
        return "# 失败复盘\n\n- 未记录\n"
    localized: list[str] = []
    key_aliases = {
        "summary": "摘要",
        "root_cause": "根因",
        "corrective_action": "纠偏动作",
        "resolution_status": "当前状态",
        "摘要": "摘要",
        "根因": "根因",
        "纠偏动作": "纠偏动作",
        "当前状态": "当前状态",
    }
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if raw_line.startswith("# Postmortems"):
            localized.append("# 失败复盘")
            continue
        if "No recorded failures yet" in raw_line:
            localized.append("当前 bootstrap 状态尚无失败复盘。后续仅追加高信号失败，记录根因、纠偏动作和当前状态。")
            continue
        if stripped.startswith("- ") and ":" in stripped:
            key, value = stripped[2:].split(":", 1)
            localized_key = key_aliases.get(key.strip(), key.strip())
            localized.append(f"- {localized_key}: {humanize_text(value.strip())}")
            continue
        localized.append(humanize_text(raw_line) if stripped and not stripped.startswith("## ") else raw_line)
    return "\n".join(localized)


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
    aliases = {
        "summary": "summary",
        "摘要": "summary",
        "root_cause": "root_cause",
        "根因": "root_cause",
        "corrective_action": "corrective_action",
        "纠偏动作": "corrective_action",
        "resolution_status": "resolution_status",
        "当前状态": "resolution_status",
    }
    for line in lines[1:]:
        stripped = line.strip()
        if stripped.startswith("- ") and ":" in stripped:
            key, value = stripped[2:].split(":", 1)
            payload[aliases.get(key.strip(), key.strip())] = value.strip()
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


def _default_iterative_loop_state() -> dict[str, Any]:
    return {
        "last_run_id": "",
        "iteration_count": 0,
        "target_iterations": 0,
        "max_iterations": 0,
        "stop_reason": "not_run",
        "direction_change": False,
        "blocker_escalation": False,
        "blocker_key": "unknown",
        "blocker_repeat_count": 0,
        "historical_blocker_count": 0,
        "blocker_history": {},
        "consecutive_no_new_info_runs": 0,
        "last_completed": "none recorded",
        "last_not_done": "none recorded",
        "next_recommendation": "none recorded",
        "subagents_used": [],
        "subagent_reason": "No iterative loop run has been recorded yet.",
        "subagent_gate_mode": "AUTO",
        "max_active_subagents": 0,
        "blocked_subagent_count": 0,
        "retired_subagent_count": 0,
        "merged_subagent_count": 0,
        "archived_subagent_count": 0,
        "canceled_subagent_count": 0,
        "refactored_subagent_count": 0,
        "auto_closed_subagents": [],
        "alternative_subagents": [],
        "artifact_path": "",
        "last_classification": "not_run",
    }


def _default_session_state(project: str, *, root: Path, paths) -> dict[str, Any]:
    base = {
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
        "iterative_loop": _default_iterative_loop_state(),
    }
    base.update(default_subagent_state(paths))
    return base


def _merge_state(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if value is None:
            continue
        merged[key] = value
    return merged


def _render_project_state(state: dict[str, Any]) -> str:
    subagents = summarize_subagent_state(state)
    stage0a = dict(state.get("stage0a_decision", {}) or {})
    lines = [
        "# 项目状态",
        "",
        f"- 当前总任务: {humanize_text(state.get('current_task', 'unknown'))}",
        f"- 当前阶段: {humanize_text(state.get('current_phase', 'unknown'))}",
        f"- 当前 blocker: {humanize_text(state.get('current_blocker', 'unknown'))}",
        f"- 当前真实能力边界: {humanize_text(state.get('current_capability_boundary', 'unknown'))}",
        f"- 下一优先动作: {humanize_text(state.get('next_priority_action', 'unknown'))}",
        f"- 最近已验证能力: {humanize_text(state.get('last_verified_capability', 'unknown'))}",
        f"- 最近失败能力: {humanize_text(state.get('last_failed_capability', 'unknown'))}",
        f"- subagent_gate_mode: {subagents['gate_mode']}",
        f"- active subagents: {', '.join(subagents['active_ids']) if subagents['active_ids'] else 'none'}",
        f"- blocked subagents: {', '.join(subagents['blocked_ids']) if subagents['blocked_ids'] else 'none'}",
        f"- 最近 subagent 事件: {humanize_text(subagents['last_event'].get('action', 'none recorded'))}",
    ]
    if stage0a:
        lines.extend(
            [
                f"- stage0a 最近决策: {humanize_text(stage0a.get('decision', 'unknown'))}",
                f"- stage0a 宇宙变化: {stage0a.get('old_universe_size', 'n/a')} -> {stage0a.get('new_universe_size', 'n/a')}",
            ],
        )
    lines.extend(["", "## 最近一次高阶迭代"])
    lines.extend(_render_loop_summary_lines(state))
    return "\n".join(lines)


def _render_hypothesis_queue(hypotheses: list[dict[str, str]]) -> str:
    lines = ["# 假设队列", ""]
    if not hypotheses:
        lines.append("1. [待处理] 尚无活跃假设。")
        return "\n".join(lines)
    status_map = {
        "pending": "待处理",
        "blocked": "阻塞",
        "active": "进行中",
        "done": "已完成",
    }
    for idx, item in enumerate(hypotheses, start=1):
        lines.append(f"{idx}. [{status_map.get(item['status'], item['status'])}] {humanize_text(item['hypothesis'])}")
    return "\n".join(lines)


def _render_verify_last(state: dict[str, Any]) -> str:
    verify = state.get("verify_last", {}) or {}
    subagents = summarize_subagent_state(state)
    passed = _normalize_list(verify.get("passed_commands"))
    failed = _normalize_list(verify.get("failed_commands"))
    lines = [
        "# 最近验证快照",
        "",
        f"- head: {state.get('head', 'unknown')}",
        f"- branch: {state.get('branch', 'unknown')}",
        "- 通过命令:",
    ]
    lines.extend([f"  - {item}" for item in passed] or ["  - 未记录"])
    lines.append("- 失败命令:")
    lines.extend([f"  - {item}" for item in failed] or ["  - 未记录"])
    lines.extend(
        [
            f"- 默认项目数据状态: {humanize_text(verify.get('default_project_data_status', 'unknown'))}",
            f"- 工程边界结论: {humanize_text(verify.get('conclusion_boundary_engineering', 'unknown'))}",
            f"- 研究边界结论: {humanize_text(verify.get('conclusion_boundary_research', 'unknown'))}",
            f"- subagent_gate_mode: {subagents['gate_mode']}",
            f"- active_subagents: {', '.join(subagents['active_ids']) if subagents['active_ids'] else 'none'}",
            f"- blocked_subagents: {', '.join(subagents['blocked_ids']) if subagents['blocked_ids'] else 'none'}",
            f"- 最近 subagent 事件: {humanize_text(subagents['last_event'].get('action', 'none recorded'))}",
            "",
            "## 高阶迭代摘要",
        ],
    )
    lines.extend(_render_loop_summary_lines(state))
    return "\n".join(lines)


def _render_handoff(state: dict[str, Any], paths) -> str:
    failure = state.get("last_failure", {}) or {}
    subagents = summarize_subagent_state(state)
    lines = [
        "# 下一轮交接",
        "",
        "## 当前总任务",
        humanize_text(state.get("current_task", "unknown")),
        "",
        "## 当前阶段",
        humanize_text(state.get("current_phase", "unknown")),
        "",
        "## 已确认路径",
        f"- tracked memory 目录: {paths.memory_dir}",
        f"- runtime meta 目录: {paths.meta_dir}",
        f"- runtime artifacts 目录: {paths.artifacts_dir}",
        "",
        "## 当前 blocker",
        humanize_text(state.get("current_blocker", "unknown")),
        "",
        "## 最近关键失败",
        humanize_text(failure.get("summary", state.get("last_failed_capability", "none recorded"))),
        "",
        "## 当前真实能力边界",
        humanize_text(state.get("current_capability_boundary", "unknown")),
        "",
        "## Subagent 状态",
        f"- gate_mode: {subagents['gate_mode']}",
        f"- active: {', '.join(subagents['active_ids']) if subagents['active_ids'] else 'none'}",
        f"- blocked: {', '.join(subagents['blocked_ids']) if subagents['blocked_ids'] else 'none'}",
        f"- recent_transition: {humanize_text(subagents['last_event'].get('action', 'none recorded'))}",
        f"- continue_using_subagents: {zh_bool(subagents['should_expand'])}",
        "",
        "## 最近一次高阶迭代",
    ]
    lines.extend(_render_loop_summary_lines(state))
    lines.extend(
        [
            "",
        "## 下一步唯一建议",
        humanize_text(state.get("next_priority_action", "unknown")),
        "",
        "## 下一轮先读这些文件",
        f"- {paths.project_state_path}",
        f"- {paths.verify_last_path}",
        f"- {paths.migration_prompt_path}",
        f"- {paths.research_memory_path}",
        ],
    )
    return "\n".join(lines)


def _render_migration_prompt(state: dict[str, Any], paths) -> str:
    failure = state.get("last_failure", {}) or {}
    verify = state.get("verify_last", {}) or {}
    subagents = summarize_subagent_state(state)
    lines = [
        "# 下一轮迁移提示",
        "",
        "## 当前总任务",
        humanize_text(state.get("current_task", "unknown")),
        "",
        "## 当前阶段",
        humanize_text(state.get("current_phase", "unknown")),
        "",
        "## 当前 Repo / Branch / HEAD",
        f"- repo_root: {paths.root}",
        f"- branch: {state.get('branch', 'unknown')}",
        f"- head: {state.get('head', 'unknown')}",
        "",
        "## 已确认事实",
        f"- tracked_memory_dir: {paths.memory_dir}",
        f"- runtime_meta_dir: {paths.meta_dir}",
        f"- runtime_artifacts_dir: {paths.artifacts_dir}",
        f"- current_blocker: {humanize_text(state.get('current_blocker', 'unknown'))}",
        "",
        "## 未确认问题",
        f"- {humanize_text('No additional unconfirmed questions have been recorded yet.')}",
        "",
        "## 最近关键失败",
        humanize_text(failure.get("summary", state.get("last_failed_capability", "none recorded"))),
        "",
        "## 当前 blocker",
        humanize_text(state.get("current_blocker", "unknown")),
        "",
        "## Subagent 状态",
        f"- gate_mode: {subagents['gate_mode']}",
        f"- active: {', '.join(subagents['active_ids']) if subagents['active_ids'] else 'none'}",
        f"- blocked: {', '.join(subagents['blocked_ids']) if subagents['blocked_ids'] else 'none'}",
        f"- recent_transition: {humanize_text(subagents['last_event'].get('action', 'none recorded'))}",
        f"- continue_using_subagents: {zh_bool(subagents['should_expand'])}",
        "",
        "## 最近一次高阶迭代",
    ]
    lines.extend(_render_loop_summary_lines(state))
    lines.extend(
        [
            "",
            "## 下一步唯一建议",
            humanize_text(state.get("next_priority_action", "unknown")),
            "",
            "## 避免重复犯错",
            f"- {humanize_text('Do not move durable memory back into ignored runtime directories.')}",
            f"- {humanize_text('Do not trust default-project research claims until validated bars exist for the frozen universe.')}",
            "",
            "## 必要验证优先",
        ],
    )
    lines.extend([f"- {item}" for item in _normalize_list(verify.get("passed_commands"))] or [f"- {humanize_text('Run the tracked-memory and contract test suite first.')}"])
    lines.extend(
        [
            "",
            "## 如果上下文变薄，先读这些文件",
            f"- {paths.project_state_path}",
            f"- {paths.verify_last_path}",
            f"- {paths.handoff_path}",
            f"- {paths.research_memory_path}",
            f"- {paths.postmortems_path}",
            "",
            "## Tracked Memory 位置",
            str(paths.memory_dir),
            "",
            "## Subagent 相关 tracked 文件",
            f"- {paths.subagent_registry_path}",
            f"- {paths.subagent_ledger_path}",
            "",
            "## Runtime Artifacts 位置",
            f"- {paths.meta_dir}",
            f"- {paths.artifacts_dir}",
            f"- {paths.subagent_artifacts_dir}",
            "",
            "## 当前真实能力边界",
            humanize_text(state.get("current_capability_boundary", "unknown")),
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


def _migrate_legacy_memory(paths, state: dict[str, Any], *, prefer_tracked_files: bool = True) -> dict[str, Any]:
    legacy = _legacy_memory_paths(paths)
    if _is_missing_or_empty(paths.project_state_path) and legacy["project_state"].exists():
        _write_text(paths.project_state_path, legacy["project_state"].read_text(encoding="utf-8"))
    if _is_missing_or_empty(paths.research_memory_path) and legacy["research_memory"].exists():
        _write_text(paths.research_memory_path, legacy["research_memory"].read_text(encoding="utf-8"))
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

    if not prefer_tracked_files:
        return state

    project_state_text = _read_text(paths.project_state_path) or _read_text(legacy["project_state"])
    parsed_state = _parse_bullet_state(project_state_text)
    if parsed_state:
        state = _merge_state(
            state,
            {
                "current_phase": parsed_state.get("phase") or parsed_state.get("current_phase") or parsed_state.get("当前阶段"),
                "current_blocker": parsed_state.get("data_status") or parsed_state.get("current_blocker") or parsed_state.get("当前 blocker"),
                "current_capability_boundary": (
                    parsed_state.get("data_status")
                    or parsed_state.get("current_real_capability_boundary")
                    or parsed_state.get("当前真实能力边界")
                    or state.get("current_capability_boundary")
                ),
                "next_priority_action": (
                    parsed_state.get("next_priority", [state.get("next_priority_action")])[0]
                    if isinstance(parsed_state.get("next_priority"), list)
                    else parsed_state.get("next_priority_action")
                    or parsed_state.get("下一优先动作")
                    or state.get("next_priority_action")
                ),
                "last_failed_capability": (
                    parsed_state.get("last_agent_cycle")
                    or parsed_state.get("最近失败能力")
                    or state.get("last_failed_capability")
                ),
            },
        )

    research_memory_text = _read_text(paths.research_memory_path) or _read_text(legacy["research_memory"])
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
    state.update({key: state.get(key) for key in default_subagent_state(paths).keys() if key in state})
    for key, value in default_subagent_state(paths).items():
        state.setdefault(key, value)
    state.setdefault("iterative_loop", _default_iterative_loop_state())
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
    loop = _iterative_loop_state(state)
    _write_text(
        paths.next_round_plan_path,
        "\n".join(
            [
                "# 下一轮研究计划",
                "",
                f"- stop_reason: {zh_stop_reason(str(loop.get('stop_reason', 'unknown')))}",
                f"- next_recommendation: {humanize_text(loop.get('next_recommendation', 'none recorded'))}",
                f"- blocker_escalation: {zh_bool(loop.get('blocker_escalation', False))}",
                f"- direction_change: {zh_bool(loop.get('direction_change', False))}",
            ],
        ),
    )
    _write_text(
        paths.portfolio_status_path,
        "\n".join(
            [
                "# 组合状态",
                "",
                f"- 当前 blocker: {humanize_text(state.get('current_blocker', 'unknown'))}",
                f"- 最近已验证能力: {humanize_text(state.get('last_verified_capability', 'unknown'))}",
                f"- 下一步建议: {humanize_text(loop.get('next_recommendation', state.get('next_priority_action', 'none recorded')))}",
            ],
        ),
    )
    _write_text(
        paths.subagent_registry_path,
        render_subagent_registry(state, role_templates=load_subagent_roles(_subagent_roles_path(paths.root))),
    )
    if paths.postmortems_path.exists():
        _write_text(paths.postmortems_path, _localize_postmortems_text(paths.postmortems_path.read_text(encoding="utf-8")))
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
        "subagent_registry": paths.subagent_registry_path,
        "subagent_ledger": paths.subagent_ledger_path,
        "mission_state": paths.mission_state_path,
        "branch_ledger": paths.branch_ledger_path,
        "evidence_ledger": paths.evidence_ledger_path,
        "portfolio_status": paths.portfolio_status_path,
        "next_round_plan": paths.next_round_plan_path,
        "memory_dir": paths.memory_dir,
        "runtime_meta_dir": paths.meta_dir,
        "runtime_cycles_dir": paths.runtime_cycles_dir,
        "runtime_subagent_artifacts_dir": paths.subagent_artifacts_dir,
        "runtime_automation_runs_dir": paths.automation_runs_dir,
    }

    session_preexisted = paths.session_state_path.exists() and bool(paths.session_state_path.read_text(encoding="utf-8").strip())
    state = _read_json(paths.session_state_path, default=_default_session_state(project, root=paths.root, paths=paths))
    state = _migrate_legacy_memory(paths, state, prefer_tracked_files=not session_preexisted)
    _write_if_missing(paths.project_state_path, PROJECT_STATE_TEMPLATE)
    _write_if_missing(paths.postmortems_path, POSTMORTEMS_TEMPLATE)
    _write_if_missing(paths.hypothesis_queue_path, HYPOTHESIS_QUEUE_TEMPLATE)
    _write_if_missing(paths.verify_last_path, VERIFY_LAST_TEMPLATE)
    if not paths.experiment_ledger_path.exists():
        paths.experiment_ledger_path.write_text("", encoding="utf-8")
    if not paths.subagent_ledger_path.exists():
        paths.subagent_ledger_path.write_text("", encoding="utf-8")
    if not paths.branch_ledger_path.exists():
        paths.branch_ledger_path.write_text("", encoding="utf-8")
    if not paths.evidence_ledger_path.exists():
        paths.evidence_ledger_path.write_text("", encoding="utf-8")
    _write_if_missing(paths.next_round_plan_path, "# Next Round Research Plan\n\n- none recorded\n")
    _write_if_missing(paths.portfolio_status_path, "# Portfolio Status\n\n- none recorded\n")
    _write_if_missing(paths.mission_state_path, json.dumps({}, ensure_ascii=False, indent=2) + "\n")
    _refresh_derived_memory(paths, state)
    return tracked_files


def _load_state(project: str, *, repo_root: Path | None = None) -> tuple[Any, dict[str, Any]]:
    bootstrap_memory_files(project, repo_root=repo_root)
    paths = resolve_project_paths(project, root=repo_root)
    state = _read_json(paths.session_state_path, default=_default_session_state(project, root=paths.root, paths=paths))
    return paths, state


def load_machine_state(project: str, *, repo_root: Path | None = None) -> tuple[Any, dict[str, Any]]:
    return _load_state(project, repo_root=repo_root)


def save_machine_state(project: str, state: dict[str, Any], *, repo_root: Path | None = None) -> Path:
    paths, _ = _load_state(project, repo_root=repo_root)
    _refresh_derived_memory(paths, state)
    return paths.session_state_path


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


def record_iterative_run(project: str, payload: dict[str, Any], *, repo_root: Path | None = None) -> dict[str, Path]:
    paths, state = _load_state(project, repo_root=repo_root)
    timestamp = str(payload.get("timestamp") or _utc_now())
    run_id = str(payload.get("run_id") or f"{project}-iterative-run")
    jsonable = to_jsonable(payload)
    paths.automation_runs_dir.mkdir(parents=True, exist_ok=True)
    run_path = paths.automation_runs_dir / f"{timestamp.replace(':', '').replace('-', '')}_{run_id}.json"
    run_path.write_text(json.dumps(jsonable, ensure_ascii=False, indent=2, sort_keys=True).rstrip() + "\n", encoding="utf-8")

    loop = _iterative_loop_state(state)
    blocker_key = str(payload.get("blocker_key", "") or "").strip()
    blocker_history = dict(loop.get("blocker_history", {}) or {})
    if blocker_key:
        history = dict(blocker_history.get(blocker_key, {}) or {})
        history["count"] = int(history.get("count", 0) or 0) + 1
        history["last_seen"] = timestamp
        history["last_stop_reason"] = str(payload.get("stop_reason", "unknown"))
        history["escalated"] = bool(payload.get("blocker_escalation", False))
        blocker_history[blocker_key] = history

    no_new_information = not bool(payload.get("new_information", True))
    consecutive_no_new_info_runs = int(loop.get("consecutive_no_new_info_runs", 0) or 0)
    loop.update(
        {
            "last_run_id": run_id,
            "iteration_count": int(payload.get("iteration_count", 0) or 0),
            "target_iterations": int(payload.get("target_iterations", 0) or 0),
            "max_iterations": int(payload.get("max_iterations", 0) or 0),
            "stop_reason": str(payload.get("stop_reason", "unknown")),
            "direction_change": bool(payload.get("direction_change", False)),
            "blocker_escalation": bool(payload.get("blocker_escalation", False)),
            "blocker_key": blocker_key or "unknown",
            "blocker_repeat_count": int(payload.get("blocker_repeat_count", 0) or 0),
            "historical_blocker_count": int(payload.get("historical_blocker_count", 0) or 0),
            "blocker_history": blocker_history,
            "consecutive_no_new_info_runs": consecutive_no_new_info_runs + 1 if no_new_information else 0,
            "last_completed": str(payload.get("completed", "none recorded")),
            "last_not_done": str(payload.get("not_done", "none recorded")),
            "next_recommendation": str(payload.get("next_recommendation", "none recorded")),
            "subagents_used": _normalize_list(payload.get("subagents_used")),
            "subagent_reason": str(payload.get("subagent_reason", "n/a")),
            "subagent_gate_mode": str(payload.get("subagent_gate_mode", "AUTO")),
            "max_active_subagents": int(payload.get("max_active_subagents", 0) or 0),
            "blocked_subagent_count": int((payload.get("subagent_status", {}) or {}).get("blocked_count", 0) or 0),
            "retired_subagent_count": int((payload.get("subagent_status", {}) or {}).get("retired_count", 0) or 0),
            "merged_subagent_count": int((payload.get("subagent_status", {}) or {}).get("merged_count", 0) or 0),
            "archived_subagent_count": int((payload.get("subagent_status", {}) or {}).get("archived_count", 0) or 0),
            "canceled_subagent_count": int((payload.get("subagent_status", {}) or {}).get("canceled_count", 0) or 0),
            "refactored_subagent_count": int((payload.get("subagent_status", {}) or {}).get("refactored_count", 0) or 0),
            "auto_closed_subagents": [
                str(item.get("subagent_id", ""))
                for item in payload.get("auto_closed_subagents", [])
                if isinstance(item, dict) and item.get("subagent_id")
            ],
            "alternative_subagents": [
                str(item.get("subagent_id", ""))
                for item in payload.get("alternative_subagents", [])
                if isinstance(item, dict) and item.get("subagent_id")
            ],
            "artifact_path": str(run_path),
            "last_classification": str(payload.get("classification", "unknown")),
        },
    )
    state["iterative_loop"] = loop
    state["current_task"] = str(payload.get("current_task") or state.get("current_task"))
    state["current_phase"] = str(payload.get("current_phase") or state.get("current_phase"))
    state["current_blocker"] = str(payload.get("current_blocker") or state.get("current_blocker"))
    state["next_priority_action"] = str(payload.get("next_recommendation") or state.get("next_priority_action"))
    if payload.get("last_verified_capability"):
        state["last_verified_capability"] = str(payload["last_verified_capability"])
    if payload.get("last_failed_capability"):
        state["last_failed_capability"] = str(payload["last_failed_capability"])
    if payload.get("current_capability_boundary"):
        state["current_capability_boundary"] = str(payload["current_capability_boundary"])

    next_step_memory = _normalize_list(state.get("next_step_memory"))
    recommendation = str(payload.get("next_recommendation", "")).strip()
    if recommendation:
        next_step_memory = [recommendation, *[item for item in next_step_memory if item != recommendation]][:5]
        state["next_step_memory"] = next_step_memory

    _refresh_derived_memory(paths, state)
    record_experiment_result(
        project,
        {
            "timestamp": timestamp,
            "experiment_id": run_id,
            "hypothesis": str(payload.get("selected_hypothesis", "")),
            "result": "passed" if bool(payload.get("verified_progress", False)) else "blocked",
            "blockers": [state.get("current_blocker", "")] if state.get("current_blocker") else [],
            "artifact_refs": [str(run_path)],
        },
        repo_root=repo_root,
    )
    if payload.get("postmortem_required"):
        record_failure(
            project,
            {
                "timestamp": timestamp,
                "experiment_id": run_id,
                "summary": str(payload.get("postmortem_summary", payload.get("not_done", ""))),
                "root_cause": str(payload.get("current_blocker", "")),
                "corrective_action": recommendation,
                "resolution_status": "not_fixed",
            },
            repo_root=repo_root,
        )
    return {
        "run_path": run_path,
        "ledger_path": paths.experiment_ledger_path,
        "session_state_path": paths.session_state_path,
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
