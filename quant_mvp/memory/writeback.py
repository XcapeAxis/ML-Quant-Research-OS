from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from ..agent.subagent_policy import load_subagent_roles
from ..agent.subagent_registry import (
    default_subagent_state,
    normalize_subagent_state,
    render_subagent_registry,
    summarize_subagent_state,
)
from ..config import load_config
from ..project import resolve_project_paths
from ..project_identity import (
    CANONICAL_PROJECT_ID,
    alias_notice,
    canonical_project_id,
    is_active_canonical_project,
    legacy_project_ids,
    rewrite_identity_payload,
)
from .ledger import append_jsonl, to_jsonable
from .localization import humanize_text, zh_bool, zh_status, zh_stop_reason
from .research_activity import (
    append_strategy_action_log,
    read_strategy_action_log,
    write_research_activity_markdown,
)
from .strategy_visibility import (
    ensure_strategy_visibility_state,
    render_strategy_board,
    render_strategy_cards,
    render_strategy_progress,
    summarize_strategy_visibility,
)
from .templates import (
    DOCS_AGENTS_TEMPLATE,
    EXECUTION_QUEUE_TEMPLATE,
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
    if path.exists() and path.is_dir():
        if any(path.iterdir()):
            raise IsADirectoryError(f"Expected file path but found non-empty directory: {path}")
        path.rmdir()
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    if path.is_dir():
        raise IsADirectoryError(f"Expected file path but found directory: {path}")
    return path.read_text(encoding="utf-8").strip()


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = text.rstrip() + "\n"
    if path.exists() and path.is_dir():
        if any(path.iterdir()):
            raise IsADirectoryError(f"Expected file path but found non-empty directory: {path}")
        path.rmdir()
    if path.exists() and path.read_text(encoding="utf-8") == normalized:
        return path
    path.write_text(normalized, encoding="utf-8")
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
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return path
    path.write_text(text, encoding="utf-8")
    return path


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


def _looks_data_blocked_text(text: str) -> bool:
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


def _looks_non_data_blocked_text(text: str) -> bool:
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
        ]
    )


def _infer_blocker_key_from_state(state: dict[str, Any]) -> str:
    blocker = str(state.get("current_blocker", "")).strip()
    blocker_lower = blocker.lower()
    verify = dict(state.get("verify_last", {}) or {})
    data_status = str(verify.get("default_project_data_status", "")).strip()
    last_failed = str(state.get("last_failed_capability", "")).strip().lower()
    data_ready = state.get("data_ready")
    if "drawdown" in blocker_lower or "回撤" in blocker:
        return "max_drawdown"
    if "leakage" in blocker_lower:
        return "leakage"
    if "walk" in blocker_lower:
        return "walk_forward"
    if "baseline" in blocker_lower or "benchmark" in blocker_lower:
        return "baseline_integrity"
    if _looks_non_data_blocked_text(blocker):
        return "strategy_contract"
    if (_looks_ready_data_status(data_status) or data_ready is True) and "drawdown" in last_failed:
        return "max_drawdown"
    if (_looks_ready_data_status(data_status) or data_ready is True) and _looks_non_data_blocked_text(last_failed):
        return "strategy_contract"
    if _looks_data_blocked_text(blocker):
        return "data_inputs"
    if _looks_data_blocked_text(data_status):
        return "data_inputs"
    if data_ready is False:
        return "data_inputs"
    return "none" if not blocker or blocker_lower in {"none", "unknown"} else blocker_lower.replace(" ", "_")[:80]


def _current_research_stage(state: dict[str, Any]) -> str:
    blocker_key = _infer_blocker_key_from_state(state)
    if blocker_key == "data_inputs":
        return "基础设施恢复"
    if blocker_key == "strategy_contract":
        return "策略契约修复"
    if blocker_key in {"max_drawdown", "leakage", "walk_forward", "baseline_integrity"}:
        return "晋级受阻"
    strategy = summarize_strategy_visibility(state)
    if strategy.get("blocked"):
        return "稳健性工作"
    return "策略验证"


def _canonical_truth_summary(state: dict[str, Any]) -> str:
    blocker = humanize_text(state.get("current_blocker", "unknown"))
    stage = _current_research_stage(state)
    if _infer_blocker_key_from_state(state) == "data_inputs":
        return f"规范项目当前仍在补研究输入，主阻塞是 {blocker}。"
    return f"规范项目当前处于{stage}阶段，真实主阻塞是 {blocker}；旧的“缺 bars”叙事已转为历史路径。"


def _drawdown_next_action(state: dict[str, Any]) -> str:
    strategy = summarize_strategy_visibility(state)
    primary = strategy.get("primary_names", []) or ["baseline_limit_up"]
    secondary = strategy.get("secondary_names", []) or ["risk_constrained_limit_up", "tighter_entry_limit_up"]
    return f"先拆解 {primary[0]} 的回撤根因，再决定优先验证 {secondary[0]} 还是 {secondary[-1]}。"


def _canonicalize_active_project_state(paths, state: dict[str, Any]) -> dict[str, Any]:
    canonical = canonical_project_id(paths.project)
    updated = rewrite_identity_payload(dict(state), project=canonical) if is_active_canonical_project(paths.project) else dict(state)
    updated["project"] = paths.project
    updated["canonical_project_id"] = canonical
    updated["legacy_project_aliases"] = legacy_project_ids(canonical)
    updated["project_identity_notice"] = alias_notice(canonical)
    try:
        cfg, _ = load_config(paths.project, config_path=paths.config_path)
        universe_policy = dict(cfg.get("universe_policy", {}) or {})
        canonical_universe_id = str(
            universe_policy.get("canonical_universe_id")
            or universe_policy.get("research_profile")
            or updated.get("canonical_universe_id")
            or "",
        ).strip()
        if canonical_universe_id:
            updated["canonical_universe_id"] = canonical_universe_id
    except Exception:
        if updated.get("canonical_universe_id"):
            updated["canonical_universe_id"] = str(updated["canonical_universe_id"]).strip()
    if is_active_canonical_project(paths.project):
        updated["baseline_status"] = str(updated.get("baseline_status") or "baseline_validation_ready")
        readiness = dict(updated.get("readiness", {}) or {})
        readiness.setdefault("stage", "validation-ready")
        readiness.setdefault("ready", True)
        updated["readiness"] = readiness
    updated["current_research_stage"] = _current_research_stage(updated)
    updated["canonical_truth_summary"] = _canonical_truth_summary(updated)
    updated["configured_subagent_gate_mode"] = str(updated.get("subagent_gate_mode", "AUTO"))
    updated["effective_subagent_gate_mode"] = str(
        ((updated.get("subagent_plan", {}) or {}).get("recommended_gate"))
        or ((updated.get("iterative_loop", {}) or {}).get("subagent_effective_gate_mode"))
        or ("OFF" if updated["configured_subagent_gate_mode"] == "OFF" else "OFF")
    )
    updated["effective_subagent_gate_reason"] = str(
        updated.get("subagent_continue_reason")
        or ((updated.get("subagent_plan", {}) or {}).get("no_split_reason"))
        or "当前没有值得安全并行拆分的工作包。"
    )
    durable_facts = _normalize_list(updated.get("durable_facts"))
    if is_active_canonical_project(paths.project):
        durable_facts = [
            item
            for item in durable_facts
            if "legacy project label `2026Q1_limit_up`" not in item
        ]
        if updated["project_identity_notice"] not in durable_facts:
            durable_facts.append(updated["project_identity_notice"])
        updated["durable_facts"] = durable_facts

    blocker_key = _infer_blocker_key_from_state(updated)
    if blocker_key == "data_inputs":
        updated["current_capability_boundary"] = "当前只能确认研究前提与数据恢复；还不能把任何候选当成已验证策略结论。"
        if "回撤" in str(updated.get("next_priority_action", "")):
            updated["next_priority_action"] = "先恢复规范项目可直接复用的 validated bars 与数据快照。"
    elif blocker_key == "strategy_contract":
        updated["current_capability_boundary"] = "当前主阻塞不是缺数据，而是控制面写回真相或策略分支契约还没有完全对齐。"
        next_action = str(updated.get("next_priority_action", "")).strip()
        if not next_action or _looks_data_blocked_text(next_action):
            updated["next_priority_action"] = "先修 tracked memory 写回真相和 branch pool -> ranking 契约，再进入因子对象层。"
        next_steps = [item for item in _normalize_list(updated.get("next_step_memory")) if not _looks_data_blocked_text(item)]
        updated["next_step_memory"] = [updated["next_priority_action"], *[item for item in next_steps if item != updated["next_priority_action"]]][:5]
    elif blocker_key == "max_drawdown":
        updated["current_capability_boundary"] = "研究输入与验证入口已就绪，当前已进入策略验证 / 晋级受阻阶段；真正卡住的是最大回撤仍高于 30%。"
        next_action = str(updated.get("next_priority_action", "")).strip()
        if not next_action or _looks_data_blocked_text(next_action):
            updated["next_priority_action"] = _drawdown_next_action(updated)
        next_steps = [item for item in _normalize_list(updated.get("next_step_memory")) if not _looks_data_blocked_text(item)]
        updated["next_step_memory"] = [updated["next_priority_action"], *[item for item in next_steps if item != updated["next_priority_action"]]][:5]
    else:
        updated["current_capability_boundary"] = str(updated.get("current_capability_boundary", "")).strip() or "当前可继续推进策略验证，但仍需保持验证口径保守。"
    return updated


def _refresh_research_activity_markdown(paths, *, run_id: str | None = None) -> None:
    entries = read_strategy_action_log(paths.strategy_action_log_path, run_id=run_id, limit=30)
    if not entries and run_id is not None:
        entries = read_strategy_action_log(paths.strategy_action_log_path, limit=30)
    write_research_activity_markdown(paths.research_activity_path, entries)


def _sync_mission_state_identity(paths) -> None:
    if not paths.mission_state_path.exists():
        return
    payload = _read_json(paths.mission_state_path, default={})
    if not payload:
        return
    if is_active_canonical_project(paths.project):
        payload = rewrite_identity_payload(payload, project=paths.project)
        payload["project"] = paths.project
        payload["mission_id"] = str(payload.get("mission_id", f"mission-{paths.project}")).replace(
            f"mission-{legacy_project_ids(paths.project)[0]}",
            f"mission-{paths.project}",
        ) if legacy_project_ids(paths.project) else str(payload.get("mission_id", f"mission-{paths.project}"))
    _write_json(paths.mission_state_path, payload)


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
    strategy = summarize_strategy_visibility(state)
    lines.extend(["", "## 仍成立的策略假设"])
    if strategy["primary"] or strategy["secondary"]:
        for item in [*strategy["primary"], *strategy["secondary"]]:
            lines.append(f"- `{item['strategy_id']}`: {item['core_hypothesis']}")
    else:
        lines.append("- 未记录")
    lines.extend(["", "## 已被削弱或否定的策略假设"])
    if strategy["rejected"]:
        for item in strategy["rejected"]:
            lines.append(f"- `{item['strategy_id']}`: {item['latest_result']}")
    else:
        lines.append("- 当前没有新增被否定的策略假设。")
    lines.extend(["", "## 负面记忆"])
    lines.extend([f"- {humanize_text(item)}" for item in negative] or ["- 未记录"])
    lines.extend(["", "## 下一步记忆"])
    lines.extend([f"- {humanize_text(item)}" for item in next_steps] or ["- 未记录"])
    lines.extend(["", *_render_strategy_snapshot_lines(state)])
    lines.extend(["", *_render_research_progress_lines(state)])
    return "\n".join(lines)


def _render_strategy_snapshot_lines(state: dict[str, Any], *, heading: str = "## 策略快照") -> list[str]:
    strategy = summarize_strategy_visibility(state)
    return [
        heading,
        f"- 当前规范项目ID: {state.get('canonical_project_id', state.get('project', 'unknown'))}",
        f"- 历史别名: {', '.join(state.get('legacy_project_aliases', [])) or '无'}",
        f"- 当前研究阶段: {state.get('current_research_stage', '未记录')}",
        f"- 当前轮次类型: {strategy['round_type']}",
        f"- 当前主线策略: {', '.join(strategy['primary_names']) or '尚未记录'}",
        f"- 当前支线策略: {', '.join(strategy['secondary_names']) or '当前为空'}",
        f"- 当前 blocked 策略: {', '.join(strategy['blocked_names']) or '当前为空'}",
        f"- 当前 rejected 策略: {', '.join(strategy['rejected_names']) or '当前为空'}",
        f"- 当前 promoted 策略: {', '.join(strategy['promoted_names']) or '当前为空'}",
        f"- 系统推进判断: {strategy['system_line']}",
        f"- 策略推进判断: {strategy['strategy_line']}",
        f"- 规范叙事结论: {humanize_text(state.get('canonical_truth_summary', 'unknown'))}",
    ]


def _recent_strategy_action_lines(paths, *, run_id: str | None = None, limit: int = 5) -> list[str]:
    entries = read_strategy_action_log(paths.strategy_action_log_path, run_id=run_id, limit=limit)
    if not entries and run_id is not None:
        entries = read_strategy_action_log(paths.strategy_action_log_path, limit=limit)
    lines = ["## 最近策略动作"]
    if not entries:
        lines.append("- 本轮未推进实质策略研究，当前没有新的策略动作记录。")
        return lines
    for item in entries:
        strategy = "本轮无实质策略研究" if item["strategy_id"] == "__none__" else item["strategy_id"]
        actor = f"{item['actor_type']}:{item['actor_id']}"
        lines.append(
            f"- {strategy} | {actor} | {humanize_text(item['action_summary'])} | 结果：{humanize_text(item['result'])} | 决策变化：{humanize_text(item['decision_delta'])}"
        )
    return lines


def _subagent_gate_lines(state: dict[str, Any]) -> list[str]:
    subagents = summarize_subagent_state(state)
    configured = str(state.get("configured_subagent_gate_mode", subagents.get("gate_mode", "AUTO")))
    effective = str(state.get("effective_subagent_gate_mode", subagents.get("recommended_gate", "OFF")))
    reason = humanize_text(state.get("effective_subagent_gate_reason", subagents.get("continue_reason", "未记录")))
    return [
        f"- configured_gate: {configured}",
        f"- effective_gate_this_run: {effective}",
        f"- gate_reason: {reason}",
    ]


_QUEUE_IMPACT_ZH = {
    "high": "高",
    "medium": "中",
    "low": "低",
}

_QUEUE_RISK_ZH = {
    "low": "低",
    "medium": "中",
    "high": "高",
}

_QUEUE_STATUS_ZH = {
    "queued": "待排队",
    "ready": "就绪",
    "in_progress": "进行中",
    "advanced": "已推进",
    "done": "已完成",
    "blocked": "阻塞",
    "deferred": "暂缓",
}


def _default_execution_queue_state() -> list[dict[str, Any]]:
    return [
        {
            "task_id": "recover_daily_bars",
            "title": "恢复默认项目可用日频 bars",
            "impact": "high",
            "risk": "low",
            "prerequisite": "无",
            "current_status": "ready",
            "owner": "main",
            "success_condition": "`data_validate` 后 blocker 缩小或 `data_ready=True`。",
            "stop_condition": "full refresh 后仍无新证据且 blocker 未缩小。",
            "action_name": "data_validate",
            "requires_data_ready": False,
        },
        {
            "task_id": "refresh_research_audit",
            "title": "刷新 repo truth 与审计基线",
            "impact": "medium",
            "risk": "low",
            "prerequisite": "以当前 blocker 重新确认 repo truth。",
            "current_status": "queued",
            "owner": "main",
            "success_condition": "审计结果让下一轮选择更确定。",
            "stop_condition": "审计结果没有带来新的边界信息。",
            "action_name": "research_audit",
            "requires_data_ready": False,
        },
        {
            "task_id": "refresh_promotion_boundary",
            "title": "刷新晋级边界诊断",
            "impact": "high",
            "risk": "medium",
            "prerequisite": "默认项目具备可研究输入。",
            "current_status": "blocked",
            "owner": "main",
            "success_condition": "promotion 失败边界被重新确认或收窄。",
            "stop_condition": "输入仍不足，继续执行 ROI 过低。",
            "action_name": "promote_candidate",
            "requires_data_ready": True,
        },
        {
            "task_id": "dry_run_agent_cycle",
            "title": "跑一次 dry-run control plane",
            "impact": "medium",
            "risk": "medium",
            "prerequisite": "默认项目具备可研究输入。",
            "current_status": "blocked",
            "owner": "main",
            "success_condition": "dry-run 结果带来新的候选或 blocker 收敛。",
            "stop_condition": "dry-run 只重复旧 blocker 且没有新信息。",
            "action_name": "agent_cycle_dry_run",
            "requires_data_ready": True,
        },
    ]


def _normalize_execution_queue(entries: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in entries or []:
        if not isinstance(raw, dict):
            continue
        task_id = str(raw.get("task_id", "")).strip()
        if not task_id:
            continue
        normalized.append(
            {
                "task_id": task_id,
                "title": str(raw.get("title", "")).strip() or task_id,
                "impact": str(raw.get("impact", "medium")).strip().lower() or "medium",
                "risk": str(raw.get("risk", "medium")).strip().lower() or "medium",
                "prerequisite": str(raw.get("prerequisite", "无")).strip() or "无",
                "current_status": str(raw.get("current_status", "queued")).strip().lower() or "queued",
                "owner": str(raw.get("owner", "main")).strip() or "main",
                "success_condition": str(raw.get("success_condition", "未记录")).strip() or "未记录",
                "stop_condition": str(raw.get("stop_condition", "未记录")).strip() or "未记录",
                "action_name": str(raw.get("action_name", "")).strip(),
                "requires_data_ready": bool(raw.get("requires_data_ready", False)),
                "selected_count": int(raw.get("selected_count", 0) or 0),
                "last_iteration": int(raw.get("last_iteration", 0) or 0),
                "last_summary": str(raw.get("last_summary", "")).strip(),
                "last_classification": str(raw.get("last_classification", "")).strip(),
            },
        )
    return normalized


def _render_execution_queue(state: dict[str, Any]) -> str:
    tasks = _normalize_execution_queue(state.get("execution_queue"))
    lines = [
        "# 执行队列",
        "",
        "| 任务ID | 标题 | 影响 | 风险 | 前置条件 | 当前状态 | Owner | 成功条件 | 停止条件 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    if not tasks:
        lines.append("| none | 未记录 | 中 | 中 | 无 | 待排队 | main | 未记录 | 未记录 |")
        return "\n".join(lines)
    for item in tasks:
        lines.append(
            "| {task_id} | {title} | {impact} | {risk} | {prerequisite} | {status} | {owner} | {success} | {stop} |".format(
                task_id=item["task_id"],
                title=humanize_text(item["title"]).replace("|", "/"),
                impact=_QUEUE_IMPACT_ZH.get(item["impact"], humanize_text(item["impact"])),
                risk=_QUEUE_RISK_ZH.get(item["risk"], humanize_text(item["risk"])),
                prerequisite=humanize_text(item["prerequisite"]).replace("|", "/"),
                status=_QUEUE_STATUS_ZH.get(item["current_status"], humanize_text(item["current_status"])),
                owner=humanize_text(item["owner"]).replace("|", "/"),
                success=humanize_text(item["success_condition"]).replace("|", "/"),
                stop=humanize_text(item["stop_condition"]).replace("|", "/"),
            ),
        )
    return "\n".join(lines)


def _iterative_loop_state(state: dict[str, Any]) -> dict[str, Any]:
    payload = dict(_default_iterative_loop_state())
    payload.update(state.get("iterative_loop", {}) or {})
    payload["subagents_used"] = _normalize_list(payload.get("subagents_used"))
    payload["blocker_history"] = dict(payload.get("blocker_history", {}) or {})
    return payload


def _render_loop_summary_lines(state: dict[str, Any]) -> list[str]:
    loop = _iterative_loop_state(state)
    configured_gate = str(state.get("configured_subagent_gate_mode", loop.get("subagent_gate_mode", "AUTO")))
    effective_gate = str(state.get("effective_subagent_gate_mode", ((state.get("subagent_plan", {}) or {}).get("recommended_gate") or "OFF")))
    return [
        f"- workflow_mode: {loop.get('workflow_mode', 'campaign')}",
        f"- target_productive_minutes: {loop.get('target_productive_minutes', 40)}",
        f"- max_runtime_mode: {loop.get('max_runtime_mode', 'bounded')}",
        f"- iteration_count: {loop.get('iteration_count', 0)}",
        f"- target_iterations: {loop.get('target_iterations', 0)}",
        f"- max_iterations: {loop.get('max_iterations', 0)}",
        f"- substantive_action_count: {loop.get('substantive_action_count', 0)} / {loop.get('target_substantive_actions', 3)}",
        f"- effective_progress_count: {loop.get('effective_progress_count', 0)}",
        f"- clarify_only_iterations: {loop.get('clarify_only_iterations', 0)} / {loop.get('clarify_only_limit', 1)}",
        f"- controlled_refresh_count: {loop.get('controlled_refresh_count', 0)} (run_start_read_count={loop.get('run_start_read_count', 0)})",
        f"- stop_reason: {zh_stop_reason(str(loop.get('stop_reason', 'unknown')))}",
        f"- direction_change: {zh_bool(loop.get('direction_change', False))}",
        f"- blocker_escalation: {zh_bool(loop.get('blocker_escalation', False))}",
        f"- blocker_key: {loop.get('blocker_key', 'unknown')} (repeat_count={loop.get('blocker_repeat_count', 0)}, historical_count={loop.get('historical_blocker_count', 0)})",
        f"- last_classification: {humanize_text(loop.get('last_classification', 'unknown'))}",
        f"- max_active_subagents: {loop.get('max_active_subagents', 0)}",
        f"- configured_subagent_gate: {configured_gate}",
        (
            f"- effective_subagent_gate: {effective_gate} "
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
        "workflow_mode": "campaign",
        "target_productive_minutes": 40,
        "max_runtime_mode": "bounded",
        "iteration_count": 0,
        "target_iterations": 0,
        "max_iterations": 0,
        "min_substantive_actions": 2,
        "target_substantive_actions": 3,
        "substantive_action_count": 0,
        "effective_progress_count": 0,
        "clarify_only_iterations": 0,
        "clarify_only_limit": 1,
        "controlled_refresh_count": 0,
        "run_start_read_count": 0,
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


_RESEARCH_PROGRESS_DIMENSIONS = (
    ("Data inputs", "data_inputs"),
    ("Strategy integrity", "strategy_integrity"),
    ("Validation stack", "validation_stack"),
    ("Promotion readiness", "promotion_readiness"),
    ("Subagent effectiveness", "subagent_effectiveness"),
)


IDEA_BACKLOG_TEMPLATE = """# 想法积压池

## 准入规则
- 原始想法先写在这里，不直接升为候选策略卡片。
- 只有同时写清楚具体假设、经济含义、所需数据和下一步验证，才允许进入 `STRATEGY_CANDIDATES/`。
- 被拒绝或暂缓的想法要保留在这里，不允许直接消失。

## Raw Ideas
- 当前为空

## Rejected / Deferred
- 当前为空
"""

_PROGRESS_STATUS_ZH = {
    "blocked": "阻塞",
    "bootstrap": "起步",
    "partial": "部分可用",
    "validation-ready": "可进入验证",
    "promotion-ready": "可进入晋级评估",
    "operational": "当前阶段可运行",
    "not-needed-yet": "当前阶段暂不需要",
}

_PROGRESS_TRAJECTORY_ZH = {
    "on-track": "在轨",
    "narrowed": "已收敛",
    "redirected": "已转向",
    "blocked": "阻塞",
}

_PROGRESS_DELTA_ZH = {
    "improved": "有改进",
    "unchanged": "无实质变化",
    "regressed": "有回退",
}

_PROGRESS_CONFIDENCE_ZH = {
    "high": "高",
    "medium": "中",
    "low": "低",
}


def _progress_status_zh(status: str) -> str:
    return _PROGRESS_STATUS_ZH.get(str(status or "").strip(), str(status or "").strip() or "未记录")


def _bounded_score(value: Any) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        score = 0
    return max(0, min(4, score))


def _dimension_payload(dimension: str, *, status: str, score: int, evidence: str) -> dict[str, Any]:
    return {
        "dimension": dimension,
        "status": str(status or "blocked").strip(),
        "score": _bounded_score(score),
        "evidence": str(evidence or "").strip() or "未记录",
    }


def _progress_signature(progress: dict[str, Any] | None) -> str:
    payload = dict(progress or {})
    return json.dumps(
        {
            "dimensions": [
                {
                    "dimension": str(item.get("dimension", "")),
                    "status": str(item.get("status", "")),
                    "score": _bounded_score(item.get("score", 0)),
                    "evidence": str(item.get("evidence", "")),
                }
                for item in payload.get("dimensions", [])
                if isinstance(item, dict)
            ],
            "overall_trajectory": str(payload.get("overall_trajectory", "")),
            "current_blocker": str(payload.get("current_blocker", "")),
            "next_milestone": str(payload.get("next_milestone", "")),
            "confidence": str(payload.get("confidence", "")),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _score_data_inputs(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    verify = dict(state.get("verify_last", {}) or {})
    data_status = str(verify.get("default_project_data_status") or payload.get("default_project_data_status") or "").strip()
    lowered = data_status.lower()
    blocker_key = str(payload.get("blocker_key") or "").strip().lower()
    data_ready = payload.get("data_ready", None)
    blocker = humanize_text(state.get("current_blocker", "unknown"))

    if (
        blocker_key == "data_inputs"
        or data_ready is False
        or any(token in lowered for token in ["missing", "blocked", "unknown", "no bars", "coverage near zero", "near zero"])
    ):
        status = "blocked" if blocker_key == "data_inputs" or data_ready is False else "bootstrap"
        evidence = f"默认项目数据状态：{humanize_text(data_status or 'unknown')}；当前 blocker：{blocker}"
        return _dimension_payload("Data inputs", status=status, score=1, evidence=evidence)
    if any(token in lowered for token in ["partial", "pilot", "fixture", "synthetic"]):
        evidence = f"默认项目数据状态：{humanize_text(data_status)}；已具备部分可用输入，但仍不足以覆盖 Phase-1 目标。"
        return _dimension_payload("Data inputs", status="partial", score=2, evidence=evidence)
    if any(token in lowered for token in ["operational", "robust", "phase-ready"]):
        evidence = f"默认项目数据状态：{humanize_text(data_status)}；当前描述已接近阶段边界可运行。"
        return _dimension_payload("Data inputs", status="operational", score=4, evidence=evidence)
    if any(token in lowered for token in ["validation-ready", "validated snapshot", "ready coverage", "research-readiness", "promotion-grade"]):
        evidence = f"默认项目数据状态：{humanize_text(data_status)}；当前输入已可支撑本阶段验证。"
        return _dimension_payload("Data inputs", status="validation-ready", score=3, evidence=evidence)
    if data_ready is True:
        evidence = f"本轮 truth 显示 data_ready=True；但缺少更强覆盖证据，按保守口径仅记为部分可用。"
        return _dimension_payload("Data inputs", status="partial", score=2, evidence=evidence)
    evidence = f"默认项目数据状态：{humanize_text(data_status or 'unknown')}；未发现足够证据支持更高评分。"
    return _dimension_payload("Data inputs", status="bootstrap", score=1, evidence=evidence)


def _score_strategy_integrity(state: dict[str, Any], payload: dict[str, Any], data_inputs: dict[str, Any]) -> dict[str, Any]:
    blocker_key = str(payload.get("blocker_key") or "").strip().lower()
    classification = str(payload.get("classification") or "").strip().lower()
    verified_progress = bool(payload.get("verified_progress", False))
    last_verified = humanize_text(state.get("last_verified_capability", "unknown"))
    last_failed = humanize_text(state.get("last_failed_capability", "unknown"))

    if blocker_key in {"leakage", "baseline_integrity"}:
        evidence = f"当前 blocker 指向 {blocker_key}；最近失败能力：{last_failed}。"
        return _dimension_payload("Strategy integrity", status="blocked", score=1, evidence=evidence)
    if verified_progress and data_inputs.get("score", 0) >= 2 and classification in {"verified_progress", "direction_corrected"}:
        evidence = f"最近已验证能力：{last_verified}；本轮已出现受控验证进展。"
        return _dimension_payload("Strategy integrity", status="validation-ready", score=3, evidence=evidence)
    evidence = f"单一研究核心与契约护栏已存在；最近已验证能力：{last_verified}。"
    return _dimension_payload("Strategy integrity", status="partial", score=2, evidence=evidence)


def _score_validation_stack(state: dict[str, Any], payload: dict[str, Any], data_inputs: dict[str, Any]) -> dict[str, Any]:
    verify = dict(state.get("verify_last", {}) or {})
    passed = _normalize_list(verify.get("passed_commands"))
    last_verified = humanize_text(state.get("last_verified_capability", "unknown"))
    if data_inputs.get("score", 0) >= 3 and passed:
        evidence = f"已记录通过命令 {len(passed)} 条；当前验证栈已可作用于本阶段真实输入。"
        return _dimension_payload("Validation stack", status="validation-ready", score=3, evidence=evidence)
    if passed or str(payload.get("classification", "")).strip():
        evidence = f"审计/泄漏/晋级框架存在；最近已验证能力：{last_verified}。"
        return _dimension_payload("Validation stack", status="partial", score=2, evidence=evidence)
    evidence = "仅具备基础验证入口，尚缺少足够已记录证据支持更高评分。"
    return _dimension_payload("Validation stack", status="bootstrap", score=1, evidence=evidence)


def _score_promotion_readiness(
    state: dict[str, Any],
    payload: dict[str, Any],
    data_inputs: dict[str, Any],
    validation_stack: dict[str, Any],
) -> dict[str, Any]:
    blocker_key = str(payload.get("blocker_key") or _infer_blocker_key_from_state(state)).strip().lower()
    blocker = humanize_text(state.get("current_blocker", "unknown"))
    if data_inputs.get("score", 0) <= 1 or blocker_key == "data_inputs":
        evidence = f"当前 blocker：{blocker}；研究输入仍不足以支撑晋级评估。"
        return _dimension_payload("Promotion readiness", status="blocked", score=1, evidence=evidence)
    if data_inputs.get("score", 0) == 2 or validation_stack.get("score", 0) <= 2:
        evidence = f"输入与验证框架仅部分可用；当前仍只能做局部晋级判断。"
        return _dimension_payload("Promotion readiness", status="partial", score=2, evidence=evidence)
    if blocker_key not in {"", "none"}:
        evidence = f"输入已可验证；当前 blocker 已转向策略或控制面问题，可进行有意义的晋级评估。"
        return _dimension_payload("Promotion readiness", status="promotion-ready", score=3, evidence=evidence)
    evidence = "输入与验证均已到位，当前阶段已接近可直接用于晋级决策。"
    return _dimension_payload("Promotion readiness", status="operational", score=4, evidence=evidence)


def _score_subagent_effectiveness(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    configured = str(payload.get("configured_subagent_gate_mode") or state.get("configured_subagent_gate_mode") or state.get("subagent_gate_mode", "AUTO")).strip()
    effective = str(payload.get("effective_subagent_gate_mode") or state.get("effective_subagent_gate_mode") or ((state.get("subagent_plan", {}) or {}).get("recommended_gate") or "OFF")).strip()
    max_active = int(payload.get("max_active_subagents", 0) or 0)
    used = _normalize_list(payload.get("subagents_used"))
    verified_progress = bool(payload.get("verified_progress", False))
    auto_closed = list(payload.get("auto_closed_subagents", []) or [])

    if max_active > 1 and used and verified_progress:
        evidence = f"本轮最大活跃 subagent 数为 {max_active}，且伴随已验证进展。"
        return _dimension_payload("Subagent effectiveness", status="operational", score=4, evidence=evidence)
    if max_active > 0 or used:
        evidence = f"本轮实际使用 subagents：{', '.join(used) or '已记录但未命名'}；存在真实任务执行证据。"
        return _dimension_payload("Subagent effectiveness", status="validation-ready", score=3, evidence=evidence)
    evidence = f"subagent 开关与收尾规则已可用，但本轮配置 gate={configured}、实际执行 gate={effective}；自动收尾 {len(auto_closed)} 个。"
    return _dimension_payload("Subagent effectiveness", status="partial", score=2, evidence=evidence)


def _classify_progress_delta(previous: dict[str, Any] | None, current: dict[str, Any], payload: dict[str, Any]) -> str:
    stop_reason = str(payload.get("stop_reason", "")).strip()
    classification = str(payload.get("classification", "")).strip().lower()
    if stop_reason == "verification_failed_scope_expanded":
        return "regressed"
    if not previous or not previous.get("dimensions"):
        if bool(payload.get("verified_progress", False)) or classification in {
            "blocker_clarified",
            "direction_corrected",
            "verified_progress",
        }:
            return "improved"
        return "unchanged"
    previous_scores = {
        str(item.get("dimension", "")): _bounded_score(item.get("score", 0))
        for item in previous.get("dimensions", [])
        if isinstance(item, dict)
    }
    current_scores = {
        str(item.get("dimension", "")): _bounded_score(item.get("score", 0))
        for item in current.get("dimensions", [])
        if isinstance(item, dict)
    }
    if any(current_scores.get(name, 0) < previous_scores.get(name, 0) for name, _ in _RESEARCH_PROGRESS_DIMENSIONS):
        return "regressed"
    if any(current_scores.get(name, 0) > previous_scores.get(name, 0) for name, _ in _RESEARCH_PROGRESS_DIMENSIONS):
        return "improved"
    previous_blocker = str(previous.get("current_blocker", "")).strip()
    current_blocker = str(current.get("current_blocker", "")).strip()
    if previous_blocker and current_blocker and previous_blocker != current_blocker and classification in {"blocker_clarified", "direction_corrected", "verified_progress"}:
        return "improved"
    return "unchanged"


def _classify_overall_trajectory(current: dict[str, Any], payload: dict[str, Any]) -> str:
    blocker_key = str(payload.get("blocker_key") or "").strip().lower()
    if payload.get("direction_change", False):
        return "redirected"
    if current.get("this_run_delta") == "regressed":
        return "blocked"
    if blocker_key in {"", "none"} and all(item.get("score", 0) >= 3 for item in current.get("dimensions", []) if isinstance(item, dict) and item.get("dimension") != "Subagent effectiveness"):
        return "on-track"
    if current.get("this_run_delta") == "improved":
        return "narrowed"
    return "blocked"


def _classify_progress_confidence(current: dict[str, Any], payload: dict[str, Any]) -> str:
    scores = {
        str(item.get("dimension", "")): _bounded_score(item.get("score", 0))
        for item in current.get("dimensions", [])
        if isinstance(item, dict)
    }
    if payload.get("verified_progress", False) and min(scores.get("Data inputs", 0), scores.get("Validation stack", 0)) >= 3:
        return "high"
    if min(scores.get("Strategy integrity", 0), scores.get("Validation stack", 0)) >= 2:
        return "medium"
    return "low"


def _build_research_progress(
    *,
    state: dict[str, Any],
    payload: dict[str, Any] | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(payload or {})
    payload.setdefault("blocker_key", _infer_blocker_key_from_state(state))
    payload.setdefault("configured_subagent_gate_mode", state.get("configured_subagent_gate_mode") or state.get("subagent_gate_mode", "AUTO"))
    payload.setdefault(
        "effective_subagent_gate_mode",
        state.get("effective_subagent_gate_mode") or ((state.get("subagent_plan", {}) or {}).get("recommended_gate") or "OFF"),
    )
    data_inputs = _score_data_inputs(state, payload)
    strategy_integrity = _score_strategy_integrity(state, payload, data_inputs)
    validation_stack = _score_validation_stack(state, payload, data_inputs)
    promotion_readiness = _score_promotion_readiness(state, payload, data_inputs, validation_stack)
    subagent_effectiveness = _score_subagent_effectiveness(state, payload)

    progress = {
        "dimensions": [
            data_inputs,
            strategy_integrity,
            validation_stack,
            promotion_readiness,
            subagent_effectiveness,
        ],
        "current_blocker": str(state.get("current_blocker", "unknown")),
        "next_milestone": str(state.get("next_priority_action", "unknown")),
    }
    progress["this_run_delta"] = _classify_progress_delta(previous, progress, payload)
    progress["overall_trajectory"] = _classify_overall_trajectory(progress, payload)
    progress["confidence"] = _classify_progress_confidence(progress, payload)
    progress["materially_changed"] = _progress_signature(previous) != _progress_signature(progress)
    return progress


def _render_research_progress_lines(state: dict[str, Any], *, heading: str = "## 研究进度") -> list[str]:
    progress = dict(state.get("research_progress", {}) or {})
    lines = [heading]
    for item in progress.get("dimensions", []):
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- {item.get('dimension', 'unknown')}: {_progress_status_zh(str(item.get('status', 'blocked')))}，"
            f"{_bounded_score(item.get('score', 0))}/4。证据：{humanize_text(item.get('evidence', 'unknown'))}"
        )
    lines.extend(
        [
            f"- 总体轨迹: {_PROGRESS_TRAJECTORY_ZH.get(str(progress.get('overall_trajectory', 'blocked')), humanize_text(progress.get('overall_trajectory', 'blocked')))}",
            f"- 本轮增量: {_PROGRESS_DELTA_ZH.get(str(progress.get('this_run_delta', 'unchanged')), humanize_text(progress.get('this_run_delta', 'unchanged')))}",
            f"- 当前 blocker: {humanize_text(progress.get('current_blocker', 'unknown'))}",
            f"- 下一里程碑: {humanize_text(progress.get('next_milestone', 'unknown'))}",
            f"- 置信度: {_PROGRESS_CONFIDENCE_ZH.get(str(progress.get('confidence', 'low')), humanize_text(progress.get('confidence', 'low')))}",
        ],
    )
    return lines


def _default_session_state(project: str, *, root: Path, paths) -> dict[str, Any]:
    canonical_universe_id = ""
    try:
        cfg, _ = load_config(project, config_path=paths.config_path)
        universe_policy = dict(cfg.get("universe_policy", {}) or {})
        canonical_universe_id = str(
            universe_policy.get("canonical_universe_id")
            or universe_policy.get("research_profile")
            or "",
        ).strip()
    except Exception:
        canonical_universe_id = ""
    base = {
        "project": project,
        "canonical_project_id": canonical_project_id(project),
        "legacy_project_aliases": legacy_project_ids(project),
        "project_identity_notice": alias_notice(project),
        "canonical_universe_id": canonical_universe_id,
        "baseline_status": "baseline_validation_ready",
        "readiness": {
            "stage": "validation-ready",
            "ready": True,
        },
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
        "execution_queue": _default_execution_queue_state(),
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
    base["configured_subagent_gate_mode"] = str(base.get("subagent_gate_mode", "AUTO"))
    base["effective_subagent_gate_mode"] = str((base.get("subagent_plan", {}) or {}).get("recommended_gate", "OFF"))
    base["effective_subagent_gate_reason"] = str(base.get("subagent_continue_reason", "unknown"))
    base["current_research_stage"] = _current_research_stage(base)
    base["canonical_truth_summary"] = _canonical_truth_summary(base)
    base["research_progress"] = _build_research_progress(state=base)
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
    strategy = summarize_strategy_visibility(state)
    lines = [
        "# 项目状态",
        "",
        f"- 当前规范项目ID: {state.get('canonical_project_id', state.get('project', 'unknown'))}",
        f"- 历史别名: {', '.join(state.get('legacy_project_aliases', [])) or '无'}",
        f"- 当前总任务: {humanize_text(state.get('current_task', 'unknown'))}",
        f"- 当前阶段: {humanize_text(state.get('current_phase', 'unknown'))}",
        f"- 当前研究阶段: {state.get('current_research_stage', '未记录')}",
        f"- 当前轮次类型: {strategy['round_type']}",
        f"- 当前主线策略: {', '.join(strategy['primary_names']) or '尚未记录'}",
        f"- 当前支线策略: {', '.join(strategy['secondary_names']) or '当前为空'}",
        f"- 当前 blocker: {humanize_text(state.get('current_blocker', 'unknown'))}",
        f"- 当前真实能力边界: {humanize_text(state.get('current_capability_boundary', 'unknown'))}",
        f"- 当前规范叙事: {humanize_text(state.get('canonical_truth_summary', 'unknown'))}",
        f"- 当前研究对象判断: {strategy['strategy_line']}",
        f"- 当前基础设施判断: {strategy['system_line']}",
        f"- 下一优先动作: {humanize_text(state.get('next_priority_action', 'unknown'))}",
        f"- 最近已验证能力: {humanize_text(state.get('last_verified_capability', 'unknown'))}",
        f"- 最近失败能力: {humanize_text(state.get('last_failed_capability', 'unknown'))}",
        *_subagent_gate_lines(state),
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
    lines.extend(["", *_render_strategy_snapshot_lines(state), "", *_render_research_progress_lines(state)])
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
    strategy = summarize_strategy_visibility(state)
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
            f"- 当前规范项目ID: {state.get('canonical_project_id', state.get('project', 'unknown'))}",
            f"- 历史别名: {', '.join(state.get('legacy_project_aliases', [])) or '无'}",
            f"- 默认项目数据状态: {humanize_text(verify.get('default_project_data_status', 'unknown'))}",
            f"- 工程边界结论: {humanize_text(verify.get('conclusion_boundary_engineering', 'unknown'))}",
            f"- 研究边界结论: {humanize_text(verify.get('conclusion_boundary_research', 'unknown'))}",
            f"- 当前研究阶段: {state.get('current_research_stage', '未记录')}",
            f"- 当前轮次类型: {strategy['round_type']}",
            f"- 当前主线策略: {', '.join(strategy['primary_names']) or '尚未记录'}",
            f"- 当前 blocked 策略: {', '.join(strategy['blocked_names']) or '当前为空'}",
            f"- 策略推进判断: {strategy['strategy_line']}",
            *_subagent_gate_lines(state),
            f"- active_subagents: {', '.join(subagents['active_ids']) if subagents['active_ids'] else 'none'}",
            f"- blocked_subagents: {', '.join(subagents['blocked_ids']) if subagents['blocked_ids'] else 'none'}",
            f"- 最近 subagent 事件: {humanize_text(subagents['last_event'].get('action', 'none recorded'))}",
            "",
            *_render_strategy_snapshot_lines(state),
            "",
            *_render_research_progress_lines(state),
            "",
            "## 高阶迭代摘要",
        ],
    )
    lines.extend(_render_loop_summary_lines(state))
    return "\n".join(lines)


def _render_handoff(state: dict[str, Any], paths) -> str:
    failure = state.get("last_failure", {}) or {}
    subagents = summarize_subagent_state(state)
    strategy = summarize_strategy_visibility(state)
    lines = [
        "# 下一轮交接",
        "",
        "## 当前总任务",
        humanize_text(state.get("current_task", "unknown")),
        "",
        "## 当前阶段",
        humanize_text(state.get("current_phase", "unknown")),
        "",
        "## 项目身份",
        f"- 当前规范项目ID: {state.get('canonical_project_id', state.get('project', 'unknown'))}",
        f"- 历史别名: {', '.join(state.get('legacy_project_aliases', [])) or '无'}",
        f"- 身份说明: {humanize_text(state.get('project_identity_notice', 'unknown'))}",
        "",
        "## 当前研究对象",
        f"- 当前研究阶段: {state.get('current_research_stage', '未记录')}",
        f"- 当前轮次类型: {strategy['round_type']}",
        f"- 当前主线策略: {', '.join(strategy['primary_names']) or '尚未记录'}",
        f"- 当前支线策略: {', '.join(strategy['secondary_names']) or '当前为空'}",
        f"- 当前 blocked 策略: {', '.join(strategy['blocked_names']) or '当前为空'}",
        f"- 当前 rejected 策略: {', '.join(strategy['rejected_names']) or '当前为空'}",
        f"- 当前策略推进判断: {strategy['strategy_line']}",
        f"- 规范叙事结论: {humanize_text(state.get('canonical_truth_summary', 'unknown'))}",
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
        *_subagent_gate_lines(state),
        f"- active: {', '.join(subagents['active_ids']) if subagents['active_ids'] else 'none'}",
        f"- blocked: {', '.join(subagents['blocked_ids']) if subagents['blocked_ids'] else 'none'}",
        f"- active_research: {', '.join(subagents['active_research_ids']) if subagents['active_research_ids'] else 'none'}",
        f"- active_infrastructure: {', '.join(subagents['active_infrastructure_ids']) if subagents['active_infrastructure_ids'] else 'none'}",
        f"- recent_transition: {humanize_text(subagents['last_event'].get('action', 'none recorded'))}",
        f"- continue_using_subagents: {zh_bool(subagents['should_expand'])}",
        "",
        "## 当前 active 研究型 subagents",
        *( [f"- {item}" for item in subagents["active_research_ids"]] if subagents["active_research_ids"] else ["- 当前为空"] ),
        "",
        *_recent_strategy_action_lines(paths, run_id=str((state.get("iterative_loop", {}) or {}).get("last_run_id", "")).strip() or None),
        "",
        *_render_research_progress_lines(state),
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
        f"- {paths.strategy_board_path}",
        f"- {paths.strategy_candidates_dir}",
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
    strategy = summarize_strategy_visibility(state)
    lines = [
        "# 下一轮迁移提示",
        "",
        "## 当前总任务",
        humanize_text(state.get("current_task", "unknown")),
        "",
        "## 当前阶段",
        humanize_text(state.get("current_phase", "unknown")),
        "",
        "## 项目身份",
        f"- canonical_project_id: {state.get('canonical_project_id', state.get('project', 'unknown'))}",
        f"- legacy_project_aliases: {', '.join(state.get('legacy_project_aliases', [])) or 'none'}",
        f"- identity_notice: {humanize_text(state.get('project_identity_notice', 'unknown'))}",
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
        f"- canonical_truth_summary: {humanize_text(state.get('canonical_truth_summary', 'unknown'))}",
        "",
        "## 当前研究对象",
        f"- current_research_stage: {state.get('current_research_stage', '未记录')}",
        f"- current_round_type: {strategy['round_type']}",
        f"- primary_strategies: {', '.join(strategy['primary_names']) or '尚未记录'}",
        f"- secondary_strategies: {', '.join(strategy['secondary_names']) or '当前为空'}",
        f"- blocked_strategies: {', '.join(strategy['blocked_names']) or '当前为空'}",
        f"- rejected_strategies: {', '.join(strategy['rejected_names']) or '当前为空'}",
        f"- promoted_strategies: {', '.join(strategy['promoted_names']) or '当前为空'}",
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
        *_subagent_gate_lines(state),
        f"- active: {', '.join(subagents['active_ids']) if subagents['active_ids'] else 'none'}",
        f"- blocked: {', '.join(subagents['blocked_ids']) if subagents['blocked_ids'] else 'none'}",
        f"- active_research: {', '.join(subagents['active_research_ids']) if subagents['active_research_ids'] else 'none'}",
        f"- active_infrastructure: {', '.join(subagents['active_infrastructure_ids']) if subagents['active_infrastructure_ids'] else 'none'}",
        f"- recent_transition: {humanize_text(subagents['last_event'].get('action', 'none recorded'))}",
        f"- continue_using_subagents: {zh_bool(subagents['should_expand'])}",
        "",
        *_recent_strategy_action_lines(paths, run_id=str((state.get("iterative_loop", {}) or {}).get("last_run_id", "")).strip() or None),
        "",
        *_render_strategy_snapshot_lines(state),
        "",
        *_render_research_progress_lines(state),
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
            f"- {paths.strategy_board_path}",
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
            "## Strategy 相关 tracked 文件",
            f"- {paths.strategy_board_path}",
            f"- {paths.strategy_candidates_dir}",
            f"- {paths.research_progress_path}",
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


def _refresh_derived_memory(paths, state: dict[str, Any], *, preserve_progress: bool = False) -> None:
    state = _canonicalize_active_project_state(paths, dict(state))
    state.update({key: state.get(key) for key in default_subagent_state(paths).keys() if key in state})
    for key, value in default_subagent_state(paths).items():
        state.setdefault(key, value)
    state = normalize_subagent_state(state)
    state.setdefault("iterative_loop", _default_iterative_loop_state())
    state["execution_queue"] = _normalize_execution_queue(state.get("execution_queue"))
    state = ensure_strategy_visibility_state(state, paths=paths)
    if preserve_progress and isinstance(state.get("research_progress"), dict) and state["research_progress"].get("dimensions"):
        state["research_progress"] = dict(state["research_progress"])
    else:
        state["research_progress"] = _build_research_progress(state=state, previous=state.get("research_progress"))
    state["head"] = _git_value(paths.root, "rev-parse", "HEAD")
    state["branch"] = _git_value(paths.root, "rev-parse", "--abbrev-ref", "HEAD")
    state["tracked_memory_dir"] = str(paths.memory_dir)
    state["runtime_meta_dir"] = str(paths.meta_dir)
    state["runtime_artifacts_dir"] = str(paths.artifacts_dir)
    state["last_updated"] = _utc_now()
    _sync_mission_state_identity(paths)
    _write_text(paths.project_state_path, _render_project_state(state))
    _write_text(paths.research_memory_path, _render_research_memory(state))
    _write_text(paths.strategy_board_path, render_strategy_board(state, paths=paths))
    _write_text(paths.research_progress_path, render_strategy_progress(state))
    _write_text(paths.hypothesis_queue_path, _render_hypothesis_queue(state.get("latest_hypotheses", [])))
    _write_text(paths.execution_queue_path, _render_execution_queue(state))
    _write_text(paths.verify_last_path, _render_verify_last(state))
    _write_text(paths.handoff_path, _render_handoff(state, paths))
    _write_text(paths.migration_prompt_path, _render_migration_prompt(state, paths))
    strategy_cards = render_strategy_cards(state, paths=paths)
    existing_cards = {path for path in paths.strategy_candidates_dir.glob("*.md")}
    for path, text in strategy_cards.items():
        _write_text(path, text)
    for stale_path in existing_cards - set(strategy_cards):
        stale_path.unlink()
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
    _refresh_research_activity_markdown(paths)
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
        "strategy_board": paths.strategy_board_path,
        "strategy_candidates_dir": paths.strategy_candidates_dir,
        "strategy_action_log": paths.strategy_action_log_path,
        "research_activity": paths.research_activity_path,
        "idea_backlog": paths.idea_backlog_path,
        "research_progress": paths.research_progress_path,
        "postmortems": paths.postmortems_path,
        "hypothesis_queue": paths.hypothesis_queue_path,
        "execution_queue": paths.execution_queue_path,
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
    state = _read_json(paths.session_state_path, default=_default_session_state(paths.project, root=paths.root, paths=paths))
    state = _migrate_legacy_memory(paths, state, prefer_tracked_files=not session_preexisted)
    _write_if_missing(paths.project_state_path, PROJECT_STATE_TEMPLATE)
    _write_if_missing(paths.postmortems_path, POSTMORTEMS_TEMPLATE)
    _write_if_missing(paths.hypothesis_queue_path, HYPOTHESIS_QUEUE_TEMPLATE)
    _write_if_missing(paths.execution_queue_path, EXECUTION_QUEUE_TEMPLATE)
    _write_if_missing(paths.verify_last_path, VERIFY_LAST_TEMPLATE)
    if not paths.experiment_ledger_path.exists():
        paths.experiment_ledger_path.write_text("", encoding="utf-8")
    if not paths.strategy_action_log_path.exists():
        paths.strategy_action_log_path.write_text("", encoding="utf-8")
    if not paths.subagent_ledger_path.exists():
        paths.subagent_ledger_path.write_text("", encoding="utf-8")
    if not paths.branch_ledger_path.exists():
        paths.branch_ledger_path.write_text("", encoding="utf-8")
    if not paths.evidence_ledger_path.exists():
        paths.evidence_ledger_path.write_text("", encoding="utf-8")
    _write_if_missing(paths.next_round_plan_path, "# Next Round Research Plan\n\n- none recorded\n")
    _write_if_missing(paths.portfolio_status_path, "# Portfolio Status\n\n- none recorded\n")
    _write_if_missing(paths.idea_backlog_path, IDEA_BACKLOG_TEMPLATE)
    _write_if_missing(paths.research_activity_path, "# 研究活动记录\n\n| 时间 | 策略 | 执行者 | 动作 | 结果 | 决策变化 |\n|---|---|---|---|---|---|\n| 未记录 | 本轮无实质策略研究 | main | 未记录 | 未记录 | 未记录 |\n")
    _write_if_missing(paths.mission_state_path, json.dumps({}, ensure_ascii=False, indent=2) + "\n")
    _refresh_derived_memory(paths, state, preserve_progress=True)
    return tracked_files


def _load_state(project: str, *, repo_root: Path | None = None) -> tuple[Any, dict[str, Any]]:
    bootstrap_memory_files(project, repo_root=repo_root)
    paths = resolve_project_paths(project, root=repo_root)
    state = _read_json(paths.session_state_path, default=_default_session_state(paths.project, root=paths.root, paths=paths))
    return paths, state


def load_machine_state(project: str, *, repo_root: Path | None = None) -> tuple[Any, dict[str, Any]]:
    return _load_state(project, repo_root=repo_root)


def save_machine_state(
    project: str,
    state: dict[str, Any],
    *,
    repo_root: Path | None = None,
    rebuild_progress: bool = True,
) -> Path:
    paths, _ = _load_state(project, repo_root=repo_root)
    state = dict(state)
    if rebuild_progress:
        state["research_progress"] = _build_research_progress(state=state, previous=state.get("research_progress"))
    _refresh_derived_memory(paths, state, preserve_progress=True)
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
    state["research_progress"] = _build_research_progress(state=state, previous=state.get("research_progress"))
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
        "project": paths.project,
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


def record_strategy_action(project: str, entry: dict[str, Any], *, repo_root: Path | None = None) -> Path:
    paths, _ = _load_state(project, repo_root=repo_root)
    payload = dict(entry)
    payload.setdefault("project_id", project)
    append_strategy_action_log(paths.strategy_action_log_path, payload)
    _refresh_research_activity_markdown(paths, run_id=str(payload.get("run_id", "")).strip() or None)
    return paths.strategy_action_log_path


def _strategy_actions_from_iterative_payload(state: dict[str, Any], payload: dict[str, Any], *, run_path: Path) -> list[dict[str, Any]]:
    strategy = summarize_strategy_visibility(state)
    primary_strategy_id = strategy.get("primary_ids", ["__none__"])[0] if strategy.get("primary_ids") else "__none__"
    run_id = str(payload.get("run_id", "unknown-run"))
    timestamp = str(payload.get("timestamp", _utc_now()))
    iterations = [item for item in payload.get("iterations", []) if isinstance(item, dict)]
    if not iterations:
        return [
            {
                "run_id": run_id,
                "project_id": str(state.get("project", "")),
                "strategy_id": "__none__",
                "actor_type": "main",
                "actor_id": "iterative_loop",
                "action_type": "infrastructure_only",
                "action_summary": "本轮未推进实质策略研究，主要在统一项目身份、阻塞叙事和报告展示。",
                "result": humanize_text(payload.get("completed", "未记录")),
                "decision_delta": "无策略结论变化；仅补齐可见性与记忆写回。",
                "artifact_refs": [str(run_path)],
                "timestamp": timestamp,
            }
        ]
    last_iteration = iterations[-1]
    action = dict(last_iteration.get("action", {}) or {})
    action_name = str(action.get("name", "")).strip()
    if action_name == "promote_candidate":
        return [
            {
                "run_id": run_id,
                "project_id": str(state.get("project", "")),
                "strategy_id": primary_strategy_id,
                "actor_type": "main",
                "actor_id": "iterative_loop",
                "action_type": "promotion_diagnostics",
                "action_summary": f"围绕 {primary_strategy_id} 刷新晋级边界诊断。",
                "result": humanize_text(payload.get("current_blocker", "未记录")),
                "decision_delta": "主线继续保留，但仍处于 blocked。",
                "artifact_refs": [str(run_path)],
                "timestamp": timestamp,
            }
        ]
    return [
        {
            "run_id": run_id,
            "project_id": str(state.get("project", "")),
            "strategy_id": "__none__",
            "actor_type": "main",
            "actor_id": "iterative_loop",
            "action_type": "infrastructure_only",
            "action_summary": "本轮没有新增策略验证，主要刷新输入、控制面或记忆结论。",
            "result": humanize_text(payload.get("completed", "未记录")),
            "decision_delta": "无新的策略结论变化。",
            "artifact_refs": [str(run_path)],
            "timestamp": timestamp,
        }
    ]


def record_failure(
    project: str,
    entry: dict[str, Any],
    *,
    repo_root: Path | None = None,
    append_ledger: bool = False,
    ledger_entry: dict[str, Any] | None = None,
    preserve_progress: bool = False,
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
    if preserve_progress and isinstance(state.get("research_progress"), dict) and state["research_progress"].get("dimensions"):
        state["research_progress"] = dict(state["research_progress"])
        _refresh_derived_memory(paths, state, preserve_progress=True)
    else:
        state["research_progress"] = _build_research_progress(state=state, previous=state.get("research_progress"))
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


def record_iterative_run(
    project: str,
    payload: dict[str, Any],
    *,
    repo_root: Path | None = None,
    state_override: dict[str, Any] | None = None,
) -> dict[str, Path]:
    paths, persisted_state = _load_state(project, repo_root=repo_root)
    previous_progress = dict(persisted_state.get("research_progress", {}) or {})
    state = _canonicalize_active_project_state(paths, dict(persisted_state))
    if state_override:
        state.update(dict(state_override))
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
            "workflow_mode": str(payload.get("workflow_mode", "campaign")),
            "target_productive_minutes": int(payload.get("target_productive_minutes", loop.get("target_productive_minutes", 40)) or 40),
            "max_runtime_mode": str(payload.get("max_runtime_mode", loop.get("max_runtime_mode", "bounded"))),
            "iteration_count": int(payload.get("iteration_count", 0) or 0),
            "target_iterations": int(payload.get("target_iterations", 0) or 0),
            "max_iterations": int(payload.get("max_iterations", 0) or 0),
            "min_substantive_actions": int(payload.get("min_substantive_actions", loop.get("min_substantive_actions", 2)) or 2),
            "target_substantive_actions": int(payload.get("target_substantive_actions", loop.get("target_substantive_actions", 3)) or 3),
            "substantive_action_count": int(payload.get("substantive_action_count", 0) or 0),
            "effective_progress_count": int(payload.get("effective_progress_count", 0) or 0),
            "clarify_only_iterations": int(payload.get("clarify_only_iterations", 0) or 0),
            "clarify_only_limit": int(payload.get("clarify_only_limit", loop.get("clarify_only_limit", 1)) or 1),
            "controlled_refresh_count": int(payload.get("controlled_refresh_count", 0) or 0),
            "run_start_read_count": int(payload.get("run_start_read_count", 0) or 0),
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
    state["configured_subagent_gate_mode"] = str((payload.get("subagent_status", {}) or {}).get("configured_gate_mode", state.get("subagent_gate_mode", "AUTO")))
    state["effective_subagent_gate_mode"] = str((payload.get("subagent_status", {}) or {}).get("effective_gate_mode", "OFF"))
    state["effective_subagent_gate_reason"] = str(payload.get("subagent_reason", state.get("subagent_continue_reason", "未记录")))

    next_step_memory = _normalize_list(state.get("next_step_memory"))
    recommendation = str(payload.get("next_recommendation", "")).strip()
    if recommendation:
        next_step_memory = [recommendation, *[item for item in next_step_memory if item != recommendation]][:5]
        state["next_step_memory"] = next_step_memory

    if "execution_queue" in payload:
        state["execution_queue"] = _normalize_execution_queue(payload.get("execution_queue"))
    state["research_progress"] = _build_research_progress(state=state, payload=payload, previous=previous_progress)
    _refresh_derived_memory(paths, state, preserve_progress=True)
    for action_entry in _strategy_actions_from_iterative_payload(state, payload, run_path=run_path):
        append_strategy_action_log(paths.strategy_action_log_path, action_entry)
    _refresh_research_activity_markdown(paths, run_id=run_id)
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
            preserve_progress=True,
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
    state["research_progress"] = _build_research_progress(state=state, previous=state.get("research_progress"))
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
