from __future__ import annotations

from pathlib import Path
from typing import Any

from ..memory.localization import humanize_text, zh_bool, zh_status
from .subagent_models import SubagentRoleTemplate


def _normalized_optional_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"none", "null", "n/a"} else text


def default_subagent_state(paths=None) -> dict[str, Any]:
    return {
        "subagent_gate_mode": "AUTO",
        "subagent_continue_recommended": False,
        "subagent_continue_reason": "默认项目的数据 blocker 还没清掉，现在扩展多个 subagent 只会增加协作成本。",
        "subagent_plan": {
            "gate_mode": "AUTO",
            "recommended_gate": "OFF",
            "recommended_count": 0,
            "recommended_roles": [],
            "work_packages": [],
            "should_expand": False,
            "no_split_reason": "当前默认项目的 blocker 还不值得为它再加一层协作开销。",
            "rationale": "在可用 validated bars 恢复前，subagent 保持有效 OFF，先不要拆分。",
            "score": 0.0,
        },
        "subagent_last_event": {},
        "subagents": [],
    }


def normalize_subagent_state(state: dict[str, Any]) -> dict[str, Any]:
    item = dict(state)
    defaults = default_subagent_state()
    plan_defaults = defaults["subagent_plan"]
    item.setdefault("subagent_gate_mode", defaults["subagent_gate_mode"])
    item.setdefault("subagent_continue_recommended", defaults["subagent_continue_recommended"])
    item.setdefault("subagent_last_event", defaults["subagent_last_event"])
    continue_reason = _normalized_optional_text(item.get("subagent_continue_reason"))
    if continue_reason in {"", "The default-project data blocker should be cleared before expanding into multiple subagents."}:
        item["subagent_continue_reason"] = defaults["subagent_continue_reason"]
    plan = dict(plan_defaults)
    plan.update(dict(item.get("subagent_plan", {}) or {}))
    if _normalized_optional_text(plan.get("no_split_reason")) in {"", "The current default-project blocker does not justify extra coordination yet."}:
        plan["no_split_reason"] = plan_defaults["no_split_reason"]
    if _normalized_optional_text(plan.get("rationale")) in {"", "Stay effectively OFF until validated bars restore independent work packages."}:
        plan["rationale"] = plan_defaults["rationale"]
    item["subagent_plan"] = plan
    item["subagents"] = normalize_subagent_records(list(item.get("subagents", [])))
    return item


def normalize_subagent_record(record: dict[str, Any]) -> dict[str, Any]:
    item = dict(record)
    strategy_id = _normalized_optional_text(item.get("strategy_id"))
    if not strategy_id:
        branch_id = _normalized_optional_text(item.get("branch_id"))
        if branch_id:
            strategy_id = branch_id
        else:
            candidate_id = _normalized_optional_text(item.get("candidate_id"))
            if candidate_id.startswith("candidate::"):
                strategy_id = candidate_id.split("::", 1)[1].strip()
    subagent_type = str(item.get("subagent_type", "")).strip().lower()
    if subagent_type not in {"research", "infrastructure"}:
        subagent_type = "research" if strategy_id else "infrastructure"
    item["subagent_type"] = subagent_type
    item["strategy_id"] = strategy_id or None
    if subagent_type == "research":
        item["research_focus"] = _normalized_optional_text(item.get("research_focus")) or _normalized_optional_text(item.get("summary"))
        item["delivered_conclusion"] = (
            _normalized_optional_text(item.get("delivered_conclusion"))
            or _normalized_optional_text(item.get("last_note"))
            or "暂无独立结论写回。"
        )
        item["decision_impact"] = (
            _normalized_optional_text(item.get("decision_impact"))
            or (f"服务策略 `{strategy_id}` 的研究推进；是否继续由主代理统一裁决。" if strategy_id else "服务具体策略研究。")
        )
    else:
        item["blocker_scope"] = (
            _normalized_optional_text(item.get("blocker_scope"))
            or _normalized_optional_text(item.get("summary"))
            or _normalized_optional_text(item.get("last_note"))
            or "未记录"
        )
        item["delivered_conclusion"] = (
            _normalized_optional_text(item.get("delivered_conclusion"))
            or _normalized_optional_text(item.get("last_note"))
            or "当前只在恢复研究前提。"
        )
        item["decision_impact"] = (
            _normalized_optional_text(item.get("decision_impact"))
            or "它不是在直接研究策略，而是在为研究恢复数据、验证或记忆前提。"
        )
    return item


def normalize_subagent_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_subagent_record(record) for record in records]


def summarize_subagent_state(state: dict[str, Any]) -> dict[str, Any]:
    state = normalize_subagent_state(state)
    records = list(state.get("subagents", []))
    active = [item["subagent_id"] for item in records if item.get("status") == "active"]
    blocked = [item["subagent_id"] for item in records if item.get("status") == "blocked"]
    retired = [item["subagent_id"] for item in records if item.get("status") == "retired"]
    merged = [item["subagent_id"] for item in records if item.get("status") == "merged"]
    archived = [item["subagent_id"] for item in records if item.get("status") == "archived"]
    canceled = [item["subagent_id"] for item in records if item.get("status") == "canceled"]
    refactored = [item["subagent_id"] for item in records if item.get("status") == "refactored"]
    transient = [item["subagent_id"] for item in records if item.get("transient", True)]
    templates = [item["subagent_id"] for item in records if not item.get("transient", True)]
    active_research = [item["subagent_id"] for item in records if item.get("status") == "active" and item.get("subagent_type") == "research"]
    active_infra = [item["subagent_id"] for item in records if item.get("status") == "active" and item.get("subagent_type") == "infrastructure"]
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
        "merged_ids": merged,
        "archived_ids": archived,
        "canceled_ids": canceled,
        "refactored_ids": refactored,
        "temporary_ids": transient,
        "template_ids": templates,
        "active_research_ids": active_research,
        "active_infrastructure_ids": active_infra,
        "last_event": last_event,
    }


def render_subagent_registry(
    state: dict[str, Any],
    *,
    role_templates: dict[str, SubagentRoleTemplate],
) -> str:
    summary = summarize_subagent_state(state)
    plan = state.get("subagent_plan", {}) or {}
    records = normalize_subagent_records(list(state.get("subagents", [])))
    lines = [
        "# Subagent 注册表",
        "",
        "## 治理概况",
        f"- gate 模式: {summary['gate_mode']}",
        f"- 建议模式: {summary['recommended_gate']}",
        f"- 是否继续使用 subagents: {zh_bool(summary['should_expand'])}",
        f"- 继续原因: {humanize_text(summary['continue_reason'])}",
        f"- 最近事件: {humanize_text(summary['last_event'].get('action', 'none recorded'))}",
        "",
        "## 当前集合",
        f"- 当前 active 实例: {', '.join(summary['active_ids']) if summary['active_ids'] else 'none'}",
        f"- 当前 blocked 实例: {', '.join(summary['blocked_ids']) if summary['blocked_ids'] else 'none'}",
        f"- 已退役: {', '.join(summary['retired_ids']) if summary['retired_ids'] else 'none'}",
        f"- 已合并: {', '.join(summary['merged_ids']) if summary['merged_ids'] else 'none'}",
        f"- 已归档: {', '.join(summary['archived_ids']) if summary['archived_ids'] else 'none'}",
        f"- 已取消: {', '.join(summary['canceled_ids']) if summary['canceled_ids'] else 'none'}",
        f"- 已重构: {', '.join(summary['refactored_ids']) if summary['refactored_ids'] else 'none'}",
        f"- 临时实例: {', '.join(summary['temporary_ids']) if summary['temporary_ids'] else 'none'}",
        f"- 长生命周期模板: {', '.join(summary['template_ids']) if summary['template_ids'] else 'none'}",
        f"- 当前 active 研究型: {', '.join(summary['active_research_ids']) if summary['active_research_ids'] else 'none'}",
        f"- 当前 active 基础设施型: {', '.join(summary['active_infrastructure_ids']) if summary['active_infrastructure_ids'] else 'none'}",
        "",
        "## 最新计划",
        f"- 建议数量: {plan.get('recommended_count', 0)}",
        f"- 建议角色: {', '.join(plan.get('recommended_roles', [])) or 'none'}",
        f"- 不拆分原因: {humanize_text(plan.get('no_split_reason', '') or 'n/a')}",
        f"- 计划理由: {humanize_text(plan.get('rationale', 'n/a'))}",
        "",
        "## 角色模板",
    ]
    for role, template in role_templates.items():
        lines.append(f"- {role}: {humanize_text(template.responsibilities[0] if template.responsibilities else 'none recorded')}")
    lines.extend(["", "## 实例记录"])
    if not records:
        lines.append("- 尚无已实例化 subagents")
        return "\n".join(lines)
    for record in records:
        type_label = "策略研究型" if record.get("subagent_type") == "research" else "基础设施型"
        lines.extend(
            [
                f"### {record['subagent_id']} | {record['role']} | {zh_status(record['status'])}",
                f"- 类型: {type_label}",
                f"- 摘要: {humanize_text(record.get('summary', ''))}",
                f"- 临时实例: {zh_bool(record.get('transient', True))}",
                (
                    f"- strategy_id: {record.get('strategy_id')}"
                    if record.get("subagent_type") == "research"
                    else f"- 服务 blocker / 前提: {humanize_text(record.get('blocker_scope', '未记录'))}"
                ),
                (
                    f"- 本轮研究内容: {humanize_text(record.get('research_focus', record.get('summary', '未记录')))}"
                    if record.get("subagent_type") == "research"
                    else f"- 基础设施任务: {humanize_text(record.get('research_focus', record.get('summary', '未记录')))}"
                ),
                f"- 交付结论: {humanize_text(record.get('delivered_conclusion', '未记录'))}",
                f"- 对策略决策的影响: {humanize_text(record.get('decision_impact', '未记录'))}",
                f"- 可写路径: {', '.join(record.get('allowed_paths', [])) or 'none'}",
                f"- 预期产物: {', '.join(record.get('expected_artifacts', [])) or 'none'}",
                f"- 产物目录: {record.get('artifact_dir') or 'n/a'}",
                f"- 关闭或最近状态说明: {humanize_text(record.get('last_note', '未记录'))}",
                f"- 生命周期: parents={', '.join(record.get('parent_ids', [])) or 'none'}; children={', '.join(record.get('child_ids', [])) or 'none'}; merged_into={record.get('merged_into') or 'n/a'}",
            ],
        )
    return "\n".join(lines)


def ensure_subagent_runtime_dir(paths, subagent_id: str) -> Path:
    path = paths.subagent_artifacts_dir / subagent_id
    path.mkdir(parents=True, exist_ok=True)
    return path
