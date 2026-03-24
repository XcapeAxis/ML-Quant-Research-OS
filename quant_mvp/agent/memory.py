from __future__ import annotations

from pathlib import Path

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
    return "\n\n".join(sections)


def project_meta_dir(project: str, *, repo_root: Path | None = None) -> Path:
    return resolve_project_paths(project, root=repo_root).meta_dir
