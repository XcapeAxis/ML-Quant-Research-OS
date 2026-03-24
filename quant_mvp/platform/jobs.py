from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from .artifacts import create_run_snapshot, should_snapshot
from .models import AppSetting, JobRun, JobStep
from .preparation import ensure_project_universe, prepare_project_data
from .schemas import ExecutionMode, JobStatus, PipelineName
from .settings import PlatformSettings


@dataclass(frozen=True)
class StepDefinition:
    key: str
    label: str
    script_rel: str = ""


@dataclass(frozen=True)
class StepExecutionResult:
    exit_code: int
    error_message: str | None = None


PIPELINE_DEFINITIONS: dict[str, tuple[StepDefinition, ...]] = {
    PipelineName.data_refresh.value: (
        StepDefinition("build_universe", "自动构建股票池"),
        StepDefinition("prepare_data", "自动准备回测数据"),
    ),
    PipelineName.signal_build.value: (
        StepDefinition("build_universe", "自动构建股票池"),
        StepDefinition("prepare_data", "自动准备回测数据"),
        StepDefinition("rank", "构建信号排序", "scripts/steps/20_build_rank.py"),
    ),
    PipelineName.backtest_only.value: (
        StepDefinition("build_universe", "自动构建股票池"),
        StepDefinition("prepare_data", "自动准备回测数据"),
        StepDefinition("rank", "构建信号排序", "scripts/steps/20_build_rank.py"),
        StepDefinition("backtest", "运行回测", "scripts/steps/30_bt_rebalance.py"),
    ),
    PipelineName.full_analysis_pack.value: (
        StepDefinition("build_universe", "自动构建股票池"),
        StepDefinition("prepare_data", "自动准备回测数据"),
        StepDefinition("rank", "构建信号排序", "scripts/steps/20_build_rank.py"),
        StepDefinition("backtest", "运行回测", "scripts/steps/30_bt_rebalance.py"),
        StepDefinition("audit", "审计数据覆盖", "scripts/audit_db.py"),
        StepDefinition("baselines", "运行基线分析", "scripts/steps/31_bt_baselines.py"),
        StepDefinition("cost", "运行成本扫描", "scripts/steps/32_cost_sweep.py"),
        StepDefinition("walk_forward", "运行滚动验证", "scripts/steps/33_walk_forward.py"),
        StepDefinition("report", "生成报告", "scripts/steps/40_make_report.py"),
    ),
}


def _utcnow() -> datetime:
    return datetime.utcnow()


def serialize_step(step: JobStep) -> dict:
    return {
        "id": step.id,
        "step_key": step.step_key,
        "label": step.label,
        "script_path": step.script_path,
        "step_order": step.step_order,
        "status": step.status,
        "exit_code": step.exit_code,
        "error_message": step.error_message,
        "started_at": step.started_at.isoformat() if step.started_at else None,
        "finished_at": step.finished_at.isoformat() if step.finished_at else None,
    }


def serialize_job(job: JobRun, include_steps: bool = True) -> dict:
    return {
        "id": job.id,
        "project": job.project_name,
        "pipeline": job.pipeline,
        "execution_mode": job.execution_mode,
        "status": job.status,
        "config_path": job.config_path,
        "log_path": job.log_path,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "snapshot_id": job.snapshot.id if job.snapshot else None,
        "steps": [serialize_step(step) for step in job.steps] if include_steps else [],
    }


class JobManager:
    def __init__(self, session_factory, settings: PlatformSettings) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._repo_root = settings.normalized_repo_root()
        self._stop_event = threading.Event()
        self._scheduler_thread: threading.Thread | None = None
        self._active_threads: dict[str, threading.Thread] = {}
        self._active_processes: dict[str, subprocess.Popen[str]] = {}
        self._lock = threading.RLock()

    @contextmanager
    def session(self):
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    def start(self) -> None:
        with self.session() as session:
            interrupted = session.query(JobRun).filter(JobRun.status.in_(["running", "cancelling"])).all()
            for job in interrupted:
                job.status = JobStatus.failed.value
                job.error_message = "平台重启前该任务尚未完成。"
                job.finished_at = _utcnow()
                for step in job.steps:
                    if step.status == JobStatus.running.value:
                        step.status = JobStatus.failed.value
                        step.error_message = "平台重启前该步骤尚未完成。"
                        step.finished_at = _utcnow()

            app_setting = session.get(AppSetting, "runtime")
            payload = {
                "mode": self._settings.mode,
                "host": self._settings.host,
                "port": self._settings.port,
                "max_concurrent_jobs": self._settings.effective_max_concurrent_jobs(),
                "proxy_url": self._settings.proxy_url,
                "ca_bundle_path": self._settings.ca_bundle_path,
            }
            if app_setting is None:
                app_setting = AppSetting(key="runtime", value_json=json.dumps(payload, ensure_ascii=False))
                session.add(app_setting)
            else:
                app_setting.value_json = json.dumps(payload, ensure_ascii=False)
                app_setting.updated_at = _utcnow()
            session.commit()

        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            name="platform-job-scheduler",
            daemon=True,
        )
        self._scheduler_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._scheduler_thread is not None:
            self._scheduler_thread.join(timeout=2)
        with self._lock:
            active = list(self._active_processes.items())
        for job_id, process in active:
            try:
                process.terminate()
            except Exception:
                pass
            self._mark_job_cancelled(job_id, "平台停止时任务仍在运行，已自动取消。")

    def submit_job(self, project: str, pipeline: str, execution_mode: str, config_path: Path) -> dict:
        steps = PIPELINE_DEFINITIONS[pipeline]
        log_dir = self._settings.resolved_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)

        with self.session() as session:
            job = JobRun(
                project_name=project,
                pipeline=pipeline,
                execution_mode=execution_mode,
                status=JobStatus.queued.value,
                config_path=str(config_path),
                log_path=str(log_dir / f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{project}_{pipeline}.log"),
            )
            session.add(job)
            session.flush()
            for step_order, step in enumerate(steps, start=1):
                session.add(
                    JobStep(
                        job_id=job.id,
                        step_key=step.key,
                        label=step.label,
                        script_path=step.script_rel,
                        step_order=step_order,
                        status="pending",
                    )
                )
            session.commit()
            session.refresh(job)
            return serialize_job(job)

    def cancel_job(self, job_id: str) -> dict:
        with self.session() as session:
            job = session.get(JobRun, job_id)
            if job is None:
                raise FileNotFoundError(job_id)
            if job.status == JobStatus.queued.value:
                job.status = JobStatus.cancelled.value
                job.finished_at = _utcnow()
                for step in job.steps:
                    if step.status == "pending":
                        step.status = JobStatus.cancelled.value
                        step.finished_at = _utcnow()
                session.commit()
                return serialize_job(job)
            if job.status == JobStatus.running.value:
                job.status = JobStatus.cancelling.value
                session.commit()
                with self._lock:
                    process = self._active_processes.get(job_id)
                if process is not None:
                    process.terminate()
                return serialize_job(job)
            return serialize_job(job)

    def _scheduler_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._schedule_once()
            except Exception:
                traceback.print_exc()
            time.sleep(0.5)

    def _schedule_once(self) -> None:
        with self.session() as session:
            queued = (
                session.query(JobRun)
                .filter(JobRun.status == JobStatus.queued.value)
                .order_by(JobRun.created_at.asc())
                .all()
            )
            if not queued:
                return

            running = (
                session.query(JobRun)
                .filter(JobRun.status.in_([JobStatus.running.value, JobStatus.cancelling.value]))
                .all()
            )
            active_projects = {job.project_name for job in running}
            active_serial = any(job.execution_mode == ExecutionMode.serial.value for job in running)
            capacity = max(0, self._settings.effective_max_concurrent_jobs() - len(running))
            if active_serial:
                return

            for job in queued:
                if job.project_name in active_projects:
                    continue
                if job.execution_mode == ExecutionMode.serial.value:
                    if running:
                        break
                    self._start_job(job.id)
                    break
                if capacity <= 0:
                    break
                self._start_job(job.id)
                capacity -= 1
                running.append(job)
                active_projects.add(job.project_name)

    def _start_job(self, job_id: str) -> None:
        with self.session() as session:
            job = session.get(JobRun, job_id)
            if job is None or job.status != JobStatus.queued.value:
                return
            job.status = JobStatus.running.value
            job.started_at = _utcnow()
            session.commit()

        thread = threading.Thread(
            target=self._run_job,
            args=(job_id,),
            name=f"platform-job-{job_id}",
            daemon=True,
        )
        with self._lock:
            self._active_threads[job_id] = thread
        thread.start()

    def _run_job(self, job_id: str) -> None:
        try:
            with self.session() as session:
                job = session.get(JobRun, job_id)
                if job is None:
                    return
                steps = list(job.steps)
                log_path = Path(job.log_path)
                project_name = job.project_name
                config_path = Path(job.config_path)
                pipeline_name = job.pipeline

            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8", errors="replace") as log_handle:
                self._write_platform_log(log_handle, f"任务开始执行：job={job_id} pipeline={pipeline_name}")

                for step in steps:
                    with self.session() as session:
                        live_job = session.get(JobRun, job_id)
                        live_step = session.get(JobStep, step.id)
                        if live_job is None or live_step is None:
                            return
                        if live_job.status == JobStatus.cancelling.value:
                            self._finish_cancelled(session, live_job, live_step, "任务在步骤开始前被取消。")
                            self._write_platform_log(log_handle, "任务在下一步开始前已取消。")
                            return
                        live_step.status = JobStatus.running.value
                        live_step.started_at = _utcnow()
                        session.commit()

                    result = self._run_step(
                        job_id=job_id,
                        step=step,
                        log_handle=log_handle,
                        config_path=config_path,
                        project=project_name,
                    )

                    with self.session() as session:
                        live_job = session.get(JobRun, job_id)
                        live_step = session.get(JobStep, step.id)
                        if live_job is None or live_step is None:
                            return

                        live_step.exit_code = result.exit_code
                        live_step.finished_at = _utcnow()
                        if live_job.status == JobStatus.cancelling.value:
                            self._finish_cancelled(session, live_job, live_step, "任务在步骤执行过程中被取消。")
                            self._write_platform_log(log_handle, "任务已取消。")
                            return

                        if result.exit_code != 0:
                            failure_message = result.error_message or f"步骤执行失败，退出码 {result.exit_code}。"
                            live_step.status = JobStatus.failed.value
                            live_step.error_message = failure_message
                            live_job.status = JobStatus.failed.value
                            live_job.error_message = f"步骤“{live_step.label}”执行失败：{failure_message}"
                            live_job.finished_at = _utcnow()
                            for trailing in live_job.steps:
                                if trailing.step_order > live_step.step_order and trailing.status == "pending":
                                    trailing.status = "skipped"
                                    trailing.finished_at = _utcnow()
                            session.commit()
                            self._write_platform_log(log_handle, f"步骤失败：{live_step.label} | {failure_message}")
                            return

                        live_step.status = JobStatus.succeeded.value
                        session.commit()
                        self._write_platform_log(log_handle, f"步骤完成：{live_step.label}")

                with self.session() as session:
                    live_job = session.get(JobRun, job_id)
                    if live_job is None:
                        return
                    if should_snapshot(live_job.pipeline):
                        create_run_snapshot(session, live_job, self._repo_root)
                        session.refresh(live_job)
                    live_job.status = JobStatus.succeeded.value
                    live_job.finished_at = _utcnow()
                    session.commit()
                    self._write_platform_log(log_handle, "任务执行完成。")
        except Exception as exc:
            traceback_text = traceback.format_exc()
            with self.session() as session:
                job = session.get(JobRun, job_id)
                if job is not None:
                    message = f"任务执行异常：{exc}"
                    job.status = JobStatus.failed.value
                    job.error_message = message
                    job.finished_at = _utcnow()
                    for step in job.steps:
                        if step.status == JobStatus.running.value:
                            step.status = JobStatus.failed.value
                            step.error_message = message
                            step.finished_at = _utcnow()
                    session.commit()
                    log_path = Path(job.log_path)
                    log_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(log_path, "a", encoding="utf-8", errors="replace") as log_handle:
                        log_handle.write(traceback_text)
        finally:
            with self._lock:
                self._active_threads.pop(job_id, None)
                self._active_processes.pop(job_id, None)

    def _run_step(
        self,
        job_id: str,
        step: JobStep,
        log_handle,
        config_path: Path,
        project: str,
    ) -> StepExecutionResult:
        if step.step_key == "build_universe":
            return self._run_build_universe_step(
                log_handle=log_handle,
                config_path=config_path,
                project=project,
            )
        if step.step_key == "prepare_data":
            return self._run_prepare_data_step(
                job_id=job_id,
                log_handle=log_handle,
                config_path=config_path,
                project=project,
            )

        exit_code = self._run_external_script(
            job_id=job_id,
            script_rel=step.script_path,
            log_handle=log_handle,
            config_path=config_path,
            project=project,
            extra_args=self._default_extra_args(step.step_key),
        )
        return StepExecutionResult(exit_code=exit_code)

    def _run_build_universe_step(
        self,
        *,
        log_handle,
        config_path: Path,
        project: str,
    ) -> StepExecutionResult:
        try:
            ensure_project_universe(
                project=project,
                config_path=config_path,
                repo_root=self._repo_root,
                script_runner=lambda script_rel, extra_args: self._run_external_script(
                    job_id="internal",
                    script_rel=script_rel,
                    log_handle=log_handle,
                    config_path=config_path,
                    project=project,
                    extra_args=extra_args,
                    track_process=False,
                ),
                log=lambda message: self._write_platform_log(log_handle, message),
            )
            return StepExecutionResult(exit_code=0)
        except Exception as exc:
            self._write_platform_log(log_handle, str(exc))
            return StepExecutionResult(exit_code=1, error_message=str(exc))

    def _run_prepare_data_step(
        self,
        *,
        job_id: str,
        log_handle,
        config_path: Path,
        project: str,
    ) -> StepExecutionResult:
        try:
            prepare_project_data(
                project=project,
                config_path=config_path,
                repo_root=self._repo_root,
                script_runner=lambda script_rel, extra_args: self._run_external_script(
                    job_id=job_id,
                    script_rel=script_rel,
                    log_handle=log_handle,
                    config_path=config_path,
                    project=project,
                    extra_args=extra_args,
                ),
                log=lambda message: self._write_platform_log(log_handle, message),
            )
            return StepExecutionResult(exit_code=0)
        except Exception as exc:
            self._write_platform_log(log_handle, str(exc))
            return StepExecutionResult(exit_code=1, error_message=str(exc))

    def _default_extra_args(self, step_key: str) -> tuple[str, ...]:
        if step_key == "backtest":
            return ("--no-show", "--save", "auto")
        return ()

    def _run_external_script(
        self,
        *,
        job_id: str,
        script_rel: str,
        log_handle,
        config_path: Path,
        project: str,
        extra_args: tuple[str, ...] = (),
        track_process: bool = True,
    ) -> int:
        if not script_rel:
            raise ValueError("脚本路径不能为空。")

        script_path = (self._repo_root / script_rel).resolve()
        cmd = [sys.executable, str(script_path), "--project", project, "--config", str(config_path), *extra_args]

        env = self._settings.network_config().apply_to_env(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        process = subprocess.Popen(
            cmd,
            cwd=self._repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
        )
        if track_process:
            with self._lock:
                self._active_processes[job_id] = process

        self._write_platform_log(log_handle, f"执行命令：{' '.join(cmd)}")
        assert process.stdout is not None
        for line in process.stdout:
            log_handle.write(line)
            log_handle.flush()

        process.wait()
        if track_process:
            with self._lock:
                self._active_processes.pop(job_id, None)
        return int(process.returncode)

    def _write_platform_log(self, log_handle, message: str) -> None:
        log_handle.write(f"[platform] {message}\n")
        log_handle.flush()

    def _finish_cancelled(self, session: Session, job: JobRun, current_step: JobStep, message: str) -> None:
        current_step.status = JobStatus.cancelled.value
        current_step.error_message = message
        current_step.finished_at = _utcnow()
        job.status = JobStatus.cancelled.value
        job.error_message = message
        job.finished_at = _utcnow()
        for trailing in job.steps:
            if trailing.step_order > current_step.step_order and trailing.status == "pending":
                trailing.status = JobStatus.cancelled.value
                trailing.finished_at = _utcnow()
        session.commit()

    def _mark_job_cancelled(self, job_id: str, message: str) -> None:
        with self.session() as session:
            job = session.get(JobRun, job_id)
            if job is None:
                return
            job.status = JobStatus.cancelled.value
            job.error_message = message
            job.finished_at = _utcnow()
            for step in job.steps:
                if step.status in {"pending", "running"}:
                    step.status = JobStatus.cancelled.value
                    step.error_message = message
                    step.finished_at = _utcnow()
            session.commit()
