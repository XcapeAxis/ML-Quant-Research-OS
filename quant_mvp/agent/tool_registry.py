from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ToolRegistry:
    approved_builtin: list[str]
    auto_installable: list[str]
    manual_approval_required: list[str]

    def is_allowed(self, tool_name: str) -> bool:
        return tool_name in self.approved_builtin


def load_tool_registry(path: Path) -> ToolRegistry:
    if not path.exists():
        return ToolRegistry(approved_builtin=[], auto_installable=[], manual_approval_required=[])
    current: str | None = None
    payload: dict[str, list[str]] = {
        "approved_builtin": [],
        "auto_installable": [],
        "manual_approval_required": [],
    }
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not raw_line.startswith(" ") and line.endswith(":"):
            key = line[:-1].strip()
            if key not in payload:
                payload[key] = []
            current = key
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and current:
            payload[current].append(stripped[2:].strip())
    return ToolRegistry(
        approved_builtin=payload.get("approved_builtin", []),
        auto_installable=payload.get("auto_installable", []),
        manual_approval_required=payload.get("manual_approval_required", []),
    )
