from __future__ import annotations

from pathlib import Path

from .project import resolve_project_paths


def load_universe_codes(project: str) -> list[str]:
    paths = resolve_project_paths(project)
    if not paths.universe_path.exists():
        raise FileNotFoundError(
            f"Universe file not found: {paths.universe_path}. Run scripts/steps/10_symbols.py first.",
        )
    with open(paths.universe_path, "r", encoding="utf-8") as handle:
        codes = [line.strip() for line in handle if line.strip()]
    return sorted(set(codes))


def save_universe_codes(project: str, codes: list[str]) -> Path:
    paths = resolve_project_paths(project)
    paths.ensure_dirs()
    with open(paths.universe_path, "w", encoding="utf-8") as handle:
        for code in sorted(set(codes)):
            handle.write(f"{str(code).zfill(6)}\n")
    return paths.universe_path
