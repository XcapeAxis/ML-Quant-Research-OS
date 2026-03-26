from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ledger import append_jsonl, to_jsonable
from .localization import humanize_text


REQUIRED_STRATEGY_ACTION_FIELDS = [
    "run_id",
    "project_id",
    "strategy_id",
    "actor_type",
    "actor_id",
    "action_type",
    "action_summary",
    "result",
    "decision_delta",
    "artifact_refs",
    "timestamp",
]


def _normalize_list(values: Any) -> list[str]:
    out: list[str] = []
    for item in values or []:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def normalize_strategy_action(entry: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "run_id": str(entry.get("run_id", "")).strip() or "unknown-run",
        "project_id": str(entry.get("project_id", "")).strip() or "unknown-project",
        "strategy_id": str(entry.get("strategy_id", "")).strip() or "__none__",
        "actor_type": str(entry.get("actor_type", "")).strip() or "main",
        "actor_id": str(entry.get("actor_id", "")).strip() or "main",
        "action_type": str(entry.get("action_type", "")).strip() or "note",
        "action_summary": str(entry.get("action_summary", "")).strip() or "未记录",
        "result": str(entry.get("result", "")).strip() or "未记录",
        "decision_delta": str(entry.get("decision_delta", "")).strip() or "未记录",
        "artifact_refs": _normalize_list(entry.get("artifact_refs")),
        "timestamp": str(entry.get("timestamp", "")).strip() or "unknown",
    }
    return payload


def append_strategy_action_log(path: Path, entry: dict[str, Any]) -> Path:
    append_jsonl(path, normalize_strategy_action(entry))
    return path


def read_strategy_action_log(path: Path, *, run_id: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
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
        if not isinstance(payload, dict):
            continue
        item = normalize_strategy_action(payload)
        if run_id and item["run_id"] != run_id:
            continue
        rows.append(item)
    if limit is not None and limit >= 0:
        rows = rows[-limit:]
    return rows


def render_research_activity(entries: list[dict[str, Any]]) -> str:
    lines = [
        "# 研究活动记录",
        "",
        "| 时间 | 策略 | 执行者 | 动作 | 结果 | 决策变化 |",
        "|---|---|---|---|---|---|",
    ]
    if not entries:
        lines.append("| 未记录 | 本轮无实质策略研究 | main | 未记录 | 未记录 | 未记录 |")
        return "\n".join(lines)
    for item in entries:
        strategy = "本轮无实质策略研究" if item["strategy_id"] == "__none__" else item["strategy_id"]
        actor = f"{item['actor_type']}:{item['actor_id']}"
        lines.append(
            "| {timestamp} | {strategy} | {actor} | {action} | {result} | {delta} |".format(
                timestamp=humanize_text(item["timestamp"]).replace("|", "/"),
                strategy=humanize_text(strategy).replace("|", "/"),
                actor=humanize_text(actor).replace("|", "/"),
                action=humanize_text(item["action_summary"]).replace("|", "/"),
                result=humanize_text(item["result"]).replace("|", "/"),
                delta=humanize_text(item["decision_delta"]).replace("|", "/"),
            ),
        )
    return "\n".join(lines)


def write_research_activity_markdown(path: Path, entries: list[dict[str, Any]]) -> Path:
    text = render_research_activity(entries).rstrip() + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def serialize_strategy_action(entry: dict[str, Any]) -> str:
    return json.dumps(to_jsonable(normalize_strategy_action(entry)), ensure_ascii=False, sort_keys=True)
