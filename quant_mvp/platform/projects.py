from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from quant_mvp.config import DEFAULT_CONFIG, load_config
from quant_mvp.project import resolve_project_paths

from .models import JobRun, PlatformProject, RunSnapshot


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def discover_projects(session: Session, repo_root: Path) -> list[PlatformProject]:
    names: set[str] = set()
    configs_root = repo_root / "configs" / "projects"
    data_root = repo_root / "data" / "projects"
    artifacts_root = repo_root / "artifacts" / "projects"

    if configs_root.exists():
        names.update(path.stem for path in configs_root.glob("*.json"))
    if data_root.exists():
        names.update(path.name for path in data_root.iterdir() if path.is_dir())
    if artifacts_root.exists():
        names.update(path.name for path in artifacts_root.iterdir() if path.is_dir())

    projects: list[PlatformProject] = []
    for name in sorted(names):
        paths = resolve_project_paths(name, root=repo_root)
        row = session.get(PlatformProject, name)
        if row is None:
            row = PlatformProject(
                name=name,
                config_path=str(paths.config_path),
                project_data_dir=str(paths.project_data_dir),
                artifacts_dir=str(paths.artifacts_dir),
                logs_dir=str(paths.logs_dir),
                config_exists="true" if paths.config_path.exists() else "false",
            )
            session.add(row)
        else:
            row.config_path = str(paths.config_path)
            row.project_data_dir = str(paths.project_data_dir)
            row.artifacts_dir = str(paths.artifacts_dir)
            row.logs_dir = str(paths.logs_dir)
            row.config_exists = "true" if paths.config_path.exists() else "false"
        projects.append(row)
    session.commit()
    return projects


def get_project_or_404(session: Session, repo_root: Path, project: str) -> PlatformProject:
    discover_projects(session, repo_root)
    row = session.get(PlatformProject, project)
    if row is None:
        raise FileNotFoundError(f"Project not found: {project}")
    return row


def _read_metrics(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return pd.read_csv(path).fillna("").to_dict(orient="records")


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _latest_artifact_summary(project: str, repo_root: Path) -> dict:
    paths = resolve_project_paths(project, root=repo_root)
    artifact_dir = paths.artifacts_dir
    meta_dir = paths.meta_dir
    images = sorted(path.name for path in artifact_dir.glob("*.png"))
    return {
        "metrics_rows": _read_metrics(artifact_dir / "summary_metrics.csv"),
        "manifest": _read_json(meta_dir / "run_manifest.json"),
        "report_markdown": _read_text(artifact_dir / "report.md"),
        "images": images,
        "files": sorted(path.name for path in artifact_dir.iterdir() if path.is_file()) if artifact_dir.exists() else [],
    }


def serialize_project(row: PlatformProject, session: Session, repo_root: Path) -> dict:
    latest_job = (
        session.query(JobRun)
        .filter(JobRun.project_name == row.name)
        .order_by(JobRun.created_at.desc())
        .first()
    )
    latest_snapshot = (
        session.query(RunSnapshot)
        .filter(RunSnapshot.project_name == row.name)
        .order_by(RunSnapshot.created_at.desc())
        .first()
    )
    artifact_summary = _latest_artifact_summary(row.name, repo_root)
    metrics_head = artifact_summary["metrics_rows"][0] if artifact_summary["metrics_rows"] else {}
    return {
        "name": row.name,
        "config_path": row.config_path,
        "config_exists": row.config_exists == "true",
        "project_data_dir": row.project_data_dir,
        "artifacts_dir": row.artifacts_dir,
        "logs_dir": row.logs_dir,
        "latest_metrics": metrics_head,
        "latest_job_id": latest_job.id if latest_job else None,
        "latest_job_status": latest_job.status if latest_job else None,
        "latest_snapshot_id": latest_snapshot.id if latest_snapshot else None,
    }


def project_detail(row: PlatformProject, session: Session, repo_root: Path) -> dict:
    payload = serialize_project(row, session, repo_root)
    payload["latest"] = _latest_artifact_summary(row.name, repo_root)
    payload["recent_runs"] = [
        {
            "job_id": snap.job_id,
            "run_id": snap.id,
            "created_at": snap.created_at.isoformat(),
        }
        for snap in session.query(RunSnapshot)
        .filter(RunSnapshot.project_name == row.name)
        .order_by(RunSnapshot.created_at.desc())
        .limit(10)
    ]
    return payload


def read_project_config(project: str, repo_root: Path) -> dict:
    paths = resolve_project_paths(project, root=repo_root)
    if not paths.config_path.exists():
        raise FileNotFoundError(f"Config not found: {paths.config_path}")
    raw = _read_json(paths.config_path)
    merged, _ = load_config(project, config_path=paths.config_path)
    return {
        "project": project,
        "config_path": str(paths.config_path),
        "raw_config": raw,
        "effective_config": merged,
        "defaults": DEFAULT_CONFIG,
    }


def write_project_config(project: str, repo_root: Path, payload: dict) -> dict:
    paths = resolve_project_paths(project, root=repo_root)
    _write_json(paths.config_path, payload)
    merged, _ = load_config(project, config_path=paths.config_path)
    return {
        "project": project,
        "config_path": str(paths.config_path),
        "raw_config": payload,
        "effective_config": merged,
        "defaults": DEFAULT_CONFIG,
    }
