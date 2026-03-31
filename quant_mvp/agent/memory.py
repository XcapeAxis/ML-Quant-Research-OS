from __future__ import annotations

from pathlib import Path

from ..experiment_graph import recent_experiment_summaries
from ..memory.writeback import bootstrap_memory_files
from ..project import resolve_project_paths


def load_memory_context(project: str, *, repo_root: Path | None = None) -> str:
    files = bootstrap_memory_files(project, repo_root=repo_root)
    sections = []
    for key, path in files.items():
        if not isinstance(path, Path):
            continue
        if path.exists() and path.suffix in {".md", ".jsonl", ".json"}:
            text = path.read_text(encoding="utf-8").strip()
            if text:
                sections.append(f"[{key}]\n{text}")
    experiment_summaries = recent_experiment_summaries(project, repo_root=repo_root, limit=3)
    if experiment_summaries:
        lines = ["[recent_experiments]"]
        for item in experiment_summaries:
            blockers = ", ".join(item.get("primary_blockers", [])) or "none"
            lines.extend(
                [
                    f"- experiment_id: {item.get('experiment_id', '')}",
                    f"  branch_id: {item.get('branch_id', '')}",
                    f"  status: {item.get('status', '')}",
                    f"  classification: {item.get('classification', '')}",
                    f"  summary: {item.get('summary', '')}",
                    f"  primary_blockers: {blockers}",
                    f"  path: {item.get('path', '')}",
                ],
            )
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def project_meta_dir(project: str, *, repo_root: Path | None = None) -> Path:
    return resolve_project_paths(project, root=repo_root).meta_dir
