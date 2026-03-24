from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .artifacts import list_project_runs, run_detail, safe_project_file, safe_snapshot_file, summarize_directory
from .db import Base, make_engine, make_session_factory
from .jobs import JobManager, serialize_job
from .models import JobRun, RunSnapshot
from .projects import (
    discover_projects,
    get_project_or_404,
    project_detail,
    read_project_config,
    serialize_project,
    write_project_config,
)
from .readiness import project_doctor, project_readiness, run_network_diagnostics
from .schemas import JobCreateRequest, PipelineName, ProjectConfigPayload
from .settings import PlatformSettings, load_platform_settings


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def create_app(settings: PlatformSettings | None = None) -> FastAPI:
    cfg = settings or load_platform_settings()
    engine = make_engine(cfg.resolved_platform_db_path())
    Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)
    manager = JobManager(session_factory=session_factory, settings=cfg)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        manager.start()
        yield
        manager.stop()

    app = FastAPI(title="BackTest Platform API", version="0.3.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.platform_settings = cfg
    app.state.session_factory = session_factory
    app.state.job_manager = manager

    def session():
        return session_factory()

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "mode": cfg.mode,
            "repo_root": str(cfg.normalized_repo_root()),
            "max_concurrent_jobs": cfg.effective_max_concurrent_jobs(),
        }

    @app.get("/api/projects")
    def list_projects():
        db = session()
        try:
            rows = discover_projects(db, cfg.normalized_repo_root())
            return [serialize_project(row, db, cfg.normalized_repo_root()) for row in rows]
        finally:
            db.close()

    @app.get("/api/projects/{project}")
    def get_project(project: str):
        db = session()
        try:
            row = get_project_or_404(db, cfg.normalized_repo_root(), project)
            return project_detail(row, db, cfg.normalized_repo_root())
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        finally:
            db.close()

    @app.get("/api/projects/{project}/config")
    def get_project_config(project: str):
        db = session()
        try:
            get_project_or_404(db, cfg.normalized_repo_root(), project)
            return read_project_config(project, cfg.normalized_repo_root())
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        finally:
            db.close()

    @app.put("/api/projects/{project}/config")
    def put_project_config(project: str, payload: ProjectConfigPayload):
        db = session()
        try:
            get_project_or_404(db, cfg.normalized_repo_root(), project)
            normalized = payload.model_dump(mode="json", exclude_unset=True)
            return write_project_config(project, cfg.normalized_repo_root(), normalized)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        finally:
            db.close()

    @app.get("/api/projects/{project}/readiness")
    def get_project_readiness(
        project: str,
        pipeline: str | None = Query(default=None),
    ):
        db = session()
        try:
            get_project_or_404(db, cfg.normalized_repo_root(), project)
            return project_readiness(settings=cfg, project=project, pipeline=pipeline)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        finally:
            db.close()

    @app.get("/api/projects/{project}/doctor")
    def get_project_doctor(
        project: str,
        pipeline: str = Query(default=PipelineName.full_analysis_pack.value),
    ):
        db = session()
        try:
            get_project_or_404(db, cfg.normalized_repo_root(), project)
            return project_doctor(settings=cfg, project=project, pipeline=pipeline)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        finally:
            db.close()

    @app.get("/api/platform/network/diagnostics")
    def get_platform_network_diagnostics():
        return run_network_diagnostics(cfg)

    @app.get("/api/projects/{project}/latest/artifacts")
    def get_latest_artifacts(project: str):
        db = session()
        try:
            row = get_project_or_404(db, cfg.normalized_repo_root(), project)
            return summarize_directory(
                Path(row.artifacts_dir),
                Path(cfg.normalized_repo_root() / "data" / "projects" / project / "meta"),
                f"/api/projects/{project}/latest/files",
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        finally:
            db.close()

    @app.get("/api/projects/{project}/latest/files/{scope}/{relative_name:path}")
    def get_latest_file(project: str, scope: str, relative_name: str):
        if scope not in {"artifacts", "meta"}:
            raise HTTPException(status_code=404, detail="不支持的文件范围。")
        try:
            path = safe_project_file(project, cfg.normalized_repo_root(), scope, relative_name)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if not path.exists():
            raise HTTPException(status_code=404, detail="文件不存在。")
        return FileResponse(path)

    @app.post("/api/jobs")
    def create_job(request: JobCreateRequest):
        db = session()
        try:
            row = get_project_or_404(db, cfg.normalized_repo_root(), request.project)
            if row.config_exists != "true":
                raise HTTPException(status_code=400, detail="该项目没有可编辑的配置文件。")

            readiness = project_readiness(
                settings=cfg,
                project=request.project,
                pipeline=request.pipeline.value,
            )
            if readiness["blocking_issues"]:
                raise HTTPException(status_code=400, detail=readiness["blocking_issues"][0])

            return manager.submit_job(
                project=request.project,
                pipeline=request.pipeline.value,
                execution_mode=request.execution_mode.value,
                config_path=Path(row.config_path),
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        finally:
            db.close()

    @app.get("/api/jobs")
    def list_jobs(project: str | None = None):
        db = session()
        try:
            query = db.query(JobRun).order_by(JobRun.created_at.desc())
            if project:
                query = query.filter(JobRun.project_name == project)
            jobs = query.limit(100).all()
            return [serialize_job(job, include_steps=False) for job in jobs]
        finally:
            db.close()

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        db = session()
        try:
            job = db.get(JobRun, job_id)
            if job is None:
                raise HTTPException(status_code=404, detail=f"未找到任务：{job_id}")
            return serialize_job(job)
        finally:
            db.close()

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        try:
            return manager.cancel_job(job_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}/events")
    def stream_job_events(job_id: str):
        def generator():
            cursor = 0
            last_status = None
            last_heartbeat = time.time()
            while True:
                db = session()
                try:
                    job = db.get(JobRun, job_id)
                    if job is None:
                        yield _sse("error", {"message": f"未找到任务：{job_id}"})
                        return
                    if last_status != job.status:
                        yield _sse("status", serialize_job(job))
                        last_status = job.status

                    log_path = Path(job.log_path)
                    if log_path.exists():
                        with open(log_path, "r", encoding="utf-8", errors="replace") as handle:
                            handle.seek(cursor)
                            for line in handle:
                                yield _sse("log", {"line": line.rstrip("\n")})
                            cursor = handle.tell()

                    if job.status in {"succeeded", "failed", "cancelled"}:
                        yield _sse("complete", serialize_job(job))
                        return
                finally:
                    db.close()

                now = time.time()
                if now - last_heartbeat >= 10:
                    yield _sse("ping", {"ts": now})
                    last_heartbeat = now
                time.sleep(1)

        return StreamingResponse(generator(), media_type="text/event-stream")

    @app.get("/api/projects/{project}/runs")
    def get_project_runs(project: str):
        db = session()
        try:
            get_project_or_404(db, cfg.normalized_repo_root(), project)
            return list_project_runs(db, project)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        finally:
            db.close()

    @app.get("/api/projects/{project}/runs/{run_id}")
    def get_run(project: str, run_id: str):
        db = session()
        try:
            return run_detail(db, project, run_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        finally:
            db.close()

    @app.get("/api/projects/{project}/runs/{run_id}/artifacts")
    def get_run_artifacts(project: str, run_id: str):
        db = session()
        try:
            detail = run_detail(db, project, run_id)
            return {
                "run_id": detail["run_id"],
                "job_id": detail["job_id"],
                "metrics_rows": detail["metrics_rows"],
                "manifest": detail["manifest"],
                "report_markdown": detail["report_markdown"],
                "images": detail["images"],
                "artifact_files": detail["artifact_files"],
                "meta_files": detail["meta_files"],
            }
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        finally:
            db.close()

    @app.get("/api/projects/{project}/runs/{run_id}/files/{scope}/{relative_name:path}")
    def get_run_file(project: str, run_id: str, scope: str, relative_name: str):
        if scope not in {"artifacts", "meta"}:
            raise HTTPException(status_code=404, detail="不支持的文件范围。")
        db = session()
        try:
            snapshot = (
                db.query(RunSnapshot)
                .filter(RunSnapshot.id == run_id, RunSnapshot.project_name == project)
                .first()
            )
            if snapshot is None:
                raise FileNotFoundError(f"未找到运行快照：{run_id}")
            path = safe_snapshot_file(snapshot, scope, relative_name)
            if not path.exists():
                raise FileNotFoundError(relative_name)
            return FileResponse(path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        finally:
            db.close()

    web_dist_dir = cfg.resolved_web_dist_dir()
    assets_dir = web_dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    def root():
        if (web_dist_dir / "index.html").exists():
            return FileResponse(web_dist_dir / "index.html")
        return RedirectResponse("/api/health")

    @app.get("/{path_name:path}")
    def spa_fallback(path_name: str, request: Request):
        del request
        if path_name.startswith("api/"):
            return JSONResponse({"detail": "未找到接口。"}, status_code=404)
        index_path = web_dist_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return JSONResponse(
            {
                "detail": "未找到前端构建产物。",
                "expected_dist": str(web_dist_dir),
            },
            status_code=404,
        )

    return app
