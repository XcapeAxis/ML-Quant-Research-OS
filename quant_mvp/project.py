from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for node in [current, *current.parents]:
        if (node / ".git").exists() or (node / "pyproject.toml").exists():
            return node
    return current


def validate_project_name(project: str) -> str:
    value = (project or "").strip()
    if not value:
        raise ValueError("project cannot be empty")
    if not PROJECT_RE.fullmatch(value):
        raise ValueError(
            "invalid project name; allowed: letters, digits, _, -, length 1-64, must start with letter/digit",
        )
    return value


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    project: str
    config_path: Path
    project_data_dir: Path
    signals_dir: Path
    features_dir: Path
    meta_dir: Path
    artifacts_dir: Path
    logs_dir: Path
    db_path: Path
    universe_path: Path

    def ensure_dirs(self) -> None:
        self.project_data_dir.mkdir(parents=True, exist_ok=True)
        self.signals_dir.mkdir(parents=True, exist_ok=True)
        self.features_dir.mkdir(parents=True, exist_ok=True)
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)


def resolve_project_paths(project: str, root: Path | None = None) -> ProjectPaths:
    repo_root = find_repo_root(root)
    name = validate_project_name(project)
    project_data_dir = repo_root / "data" / "projects" / name
    meta_dir = project_data_dir / "meta"
    return ProjectPaths(
        root=repo_root,
        project=name,
        config_path=repo_root / "configs" / "projects" / f"{name}.json",
        project_data_dir=project_data_dir,
        signals_dir=project_data_dir / "signals",
        features_dir=project_data_dir / "features",
        meta_dir=meta_dir,
        artifacts_dir=repo_root / "artifacts" / "projects" / name,
        logs_dir=repo_root / "logs" / "projects" / name,
        db_path=repo_root / "data" / "market.db",
        universe_path=meta_dir / "universe_codes.txt",
    )
