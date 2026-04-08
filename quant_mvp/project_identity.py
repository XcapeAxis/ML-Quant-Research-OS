from __future__ import annotations

from pathlib import Path
from typing import Any


CANONICAL_PROJECT_ID = "crypto_okx_research_v1"
LEGACY_PROJECT_ALIASES = {
    "2026Q1_limit_up": "as_share_research_v1",
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
        return "Current project has no legacy aliases."
    return f"Legacy project aliases: {', '.join(aliases)}. Keep them only for migration and archive references."


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
            f"- Legacy project label: `{legacy_project}`",
            f"- Current canonical project: `{canonical_project}`",
            "- Current state: archived reference only. Keep it for migration notes and old experiment context.",
            "- Archive reason: the active research line has moved elsewhere, so this legacy label no longer carries the live blocker or the active strategy decision.",
            f"- Canonical blocker now: {current_blocker}",
            "- Usage rule: if you need current research, verification, handoff, migration prompt, or session state, read and write the canonical project directory only.",
            "- Compatibility boundary: the legacy label may still appear in old experiment references, migration notes, and archive comments only.",
        ],
    )


def canonical_project_paths(root: Path) -> dict[str, Path]:
    return {
        "tracked_memory": root / "memory" / "projects" / CANONICAL_PROJECT_ID,
        "runtime_meta": root / "data" / "projects" / CANONICAL_PROJECT_ID / "meta",
        "runtime_artifacts": root / "artifacts" / "projects" / CANONICAL_PROJECT_ID,
    }
