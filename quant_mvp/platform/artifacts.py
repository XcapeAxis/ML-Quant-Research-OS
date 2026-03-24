from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from quant_mvp.config import load_config
from quant_mvp.project import resolve_project_paths

from .models import JobRun, RunSnapshot


def _safe_join(root: Path, relative_name: str) -> Path:
    candidate = (root / relative_name).resolve()
    if root.resolve() not in candidate.parents and candidate != root.resolve():
        raise FileNotFoundError(relative_name)
    return candidate


def safe_project_file(project: str, repo_root: Path, scope: str, relative_name: str) -> Path:
    paths = resolve_project_paths(project, root=repo_root)
    root = paths.artifacts_dir if scope == "artifacts" else paths.meta_dir
    return _safe_join(root, relative_name)


def safe_snapshot_file(snapshot: RunSnapshot, scope: str, relative_name: str) -> Path:
    root = Path(snapshot.artifacts_dir) if scope == "artifacts" else Path(snapshot.meta_dir)
    return _safe_join(root, relative_name)


def summarize_directory(artifacts_dir: Path, meta_dir: Path, file_base_url: str) -> dict:
    metrics_path = artifacts_dir / "summary_metrics.csv"
    report_path = artifacts_dir / "report.md"
    manifest_path = meta_dir / "run_manifest.json"
    images = sorted(path.name for path in artifacts_dir.glob("*.png"))
    files = sorted(path.name for path in artifacts_dir.iterdir() if path.is_file()) if artifacts_dir.exists() else []
    meta_files = sorted(path.name for path in meta_dir.iterdir() if path.is_file()) if meta_dir.exists() else []

    metrics_rows = pd.read_csv(metrics_path).fillna("").to_dict(orient="records") if metrics_path.exists() else []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    report_markdown = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    return {
        "metrics_rows": metrics_rows,
        "manifest": manifest,
        "report_markdown": report_markdown,
        "images": [
            {"name": name, "url": f"{file_base_url}/artifacts/{name}"}
            for name in images
        ],
        "artifact_files": [
            {"name": name, "url": f"{file_base_url}/artifacts/{name}"}
            for name in files
        ],
        "meta_files": [
            {"name": name, "url": f"{file_base_url}/meta/{name}"}
            for name in meta_files
        ],
    }


def should_snapshot(pipeline: str) -> bool:
    return pipeline in {"backtest_only", "full_analysis_pack"}


def create_run_snapshot(session: Session, job: JobRun, repo_root: Path) -> RunSnapshot:
    existing = session.query(RunSnapshot).filter(RunSnapshot.job_id == job.id).first()
    if existing is not None:
        return existing

    paths = resolve_project_paths(job.project_name, root=repo_root)
    run_artifacts_dir = paths.artifacts_dir / "runs" / job.id
    run_meta_dir = paths.project_data_dir / "runs" / job.id / "meta"
    run_artifacts_dir.mkdir(parents=True, exist_ok=True)
    run_meta_dir.mkdir(parents=True, exist_ok=True)

    if paths.artifacts_dir.exists():
        for file_path in paths.artifacts_dir.iterdir():
            if file_path.is_file():
                shutil.copy2(file_path, run_artifacts_dir / file_path.name)

    if paths.meta_dir.exists():
        for file_path in paths.meta_dir.iterdir():
            if file_path.is_file():
                shutil.copy2(file_path, run_meta_dir / file_path.name)

    merged_cfg, _ = load_config(job.project_name, config_path=Path(job.config_path))
    config_snapshot_path = run_meta_dir / "config.snapshot.json"
    config_snapshot_path.write_text(
        json.dumps(merged_cfg, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    snapshot = RunSnapshot(
        id=job.id,
        job_id=job.id,
        project_name=job.project_name,
        artifacts_dir=str(run_artifacts_dir),
        meta_dir=str(run_meta_dir),
        config_snapshot_path=str(config_snapshot_path),
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return snapshot


def list_project_runs(session: Session, project: str) -> list[dict]:
    runs = (
        session.query(RunSnapshot, JobRun)
        .join(JobRun, JobRun.id == RunSnapshot.job_id)
        .filter(RunSnapshot.project_name == project)
        .order_by(RunSnapshot.created_at.desc())
        .all()
    )
    payload: list[dict] = []
    for snapshot, job in runs:
        summary = summarize_directory(
            Path(snapshot.artifacts_dir),
            Path(snapshot.meta_dir),
            f"/api/projects/{project}/runs/{snapshot.id}/files",
        )
        payload.append(
            {
                "run_id": snapshot.id,
                "job_id": job.id,
                "pipeline": job.pipeline,
                "status": job.status,
                "created_at": snapshot.created_at.isoformat(),
                "metrics_rows": summary["metrics_rows"],
                "images": summary["images"],
            }
        )
    return payload


def run_detail(session: Session, project: str, run_id: str) -> dict:
    snapshot = session.query(RunSnapshot).filter(RunSnapshot.id == run_id, RunSnapshot.project_name == project).first()
    if snapshot is None:
        raise FileNotFoundError(f"Run not found: {run_id}")
    job = session.query(JobRun).filter(JobRun.id == snapshot.job_id).first()
    summary = summarize_directory(
        Path(snapshot.artifacts_dir),
        Path(snapshot.meta_dir),
        f"/api/projects/{project}/runs/{snapshot.id}/files",
    )
    return {
        "run_id": snapshot.id,
        "job_id": job.id if job else snapshot.job_id,
        "project": project,
        "pipeline": job.pipeline if job else "",
        "status": job.status if job else "succeeded",
        "created_at": snapshot.created_at.isoformat(),
        "artifacts_dir": snapshot.artifacts_dir,
        "meta_dir": snapshot.meta_dir,
        "config_snapshot_path": snapshot.config_snapshot_path,
        **summary,
    }
