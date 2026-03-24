from __future__ import annotations

from typing import Any


def apply_merge_transition(
    *,
    source: dict[str, Any],
    target: dict[str, Any],
    summary: str,
    timestamp: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_record = dict(source)
    target_record = dict(target)
    source_record["status"] = "merged"
    source_record["merged_into"] = target_record["subagent_id"]
    source_record["updated_at"] = timestamp
    source_record["last_action"] = "merge"
    source_record["last_note"] = summary
    target_children = list(target_record.get("child_ids", []))
    if source_record["subagent_id"] not in target_children:
        target_children.append(source_record["subagent_id"])
    target_record["child_ids"] = target_children
    target_record["updated_at"] = timestamp
    target_record["last_action"] = "merge_target"
    target_record["last_note"] = summary
    return source_record, target_record
