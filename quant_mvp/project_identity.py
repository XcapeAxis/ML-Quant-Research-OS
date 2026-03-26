from __future__ import annotations

from pathlib import Path
from typing import Any


CANONICAL_PROJECT_ID = "as_share_research_v1"
LEGACY_PROJECT_ALIASES = {
    "2026Q1_limit_up": CANONICAL_PROJECT_ID,
}


def canonical_project_id(project: str) -> str:
    value = str(project or "").strip()
    return LEGACY_PROJECT_ALIASES.get(value, value)


def legacy_project_ids(project: str) -> list[str]:
    canonical = canonical_project_id(project)
    return [legacy for legacy, target in LEGACY_PROJECT_ALIASES.items() if target == canonical]


def is_active_canonical_project(project: str) -> bool:
    return str(project or "").strip() == CANONICAL_PROJECT_ID


def alias_notice(project: str) -> str:
    aliases = legacy_project_ids(project)
    if not aliases:
        return "当前项目没有已知历史别名。"
    return f"历史项目名 {', '.join(aliases)} 仅作为 legacy alias / 迁移记录保留，不再代表当前活跃项目。"


def rewrite_identity_text(text: str, *, project: str) -> str:
    value = str(text or "")
    canonical = canonical_project_id(project)
    if not value or not canonical:
        return value
    for legacy in legacy_project_ids(canonical):
        replacements = {
            f"mission-{legacy}": f"mission-{canonical}",
            f"{legacy}__": f"{canonical}__",
            f"/projects/{legacy}/": f"/projects/{canonical}/",
            f"\\projects\\{legacy}\\": f"\\projects\\{canonical}\\",
            f"/projects/{legacy}\\": f"/projects/{canonical}\\",
            f"\\projects\\{legacy}/": f"\\projects\\{canonical}/",
        }
        for source, target in replacements.items():
            value = value.replace(source, target)
    return value


def rewrite_identity_payload(payload: Any, *, project: str) -> Any:
    canonical = canonical_project_id(project)
    if isinstance(payload, dict):
        return {
            key: rewrite_identity_payload(
                canonical if key == "project" and str(value or "").strip() in legacy_project_ids(canonical) else value,
                project=canonical,
            )
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [rewrite_identity_payload(item, project=canonical) for item in payload]
    if isinstance(payload, str):
        return rewrite_identity_text(payload, project=canonical)
    return payload


def legacy_archive_markdown(*, legacy_project: str, canonical_project: str, current_blocker: str) -> str:
    return "\n".join(
        [
            f"# Legacy Archive: {legacy_project}",
            "",
            f"- 历史项目名: `{legacy_project}`",
            f"- 当前规范项目名: `{canonical_project}`",
            "- 当前状态: 已归档，仅保留历史迁移与兼容说明。",
            "- 归档原因: 当前活跃研究已经统一到规范项目名下，旧项目名不再承载活跃 blocker 或当前研究结论。",
            f"- 当前规范项目的真实 blocker: {current_blocker}",
            "- 使用规则: 如果需要继续研究、验证、handoff、migration prompt、verify snapshot 或 session state，请只读写规范项目名目录。",
            "- 兼容边界: 旧项目名只允许继续出现在 legacy alias、迁移说明、历史实验引用或归档注释中。",
        ],
    )


def canonical_project_paths(root: Path) -> dict[str, Path]:
    return {
        "tracked_memory": root / "memory" / "projects" / CANONICAL_PROJECT_ID,
        "runtime_meta": root / "data" / "projects" / CANONICAL_PROJECT_ID / "meta",
        "runtime_artifacts": root / "artifacts" / "projects" / CANONICAL_PROJECT_ID,
    }
