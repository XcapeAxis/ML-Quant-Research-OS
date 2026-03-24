from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _job_id() -> str:
    return uuid4().hex


class PlatformProject(Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    config_path: Mapped[str] = mapped_column(Text, nullable=False)
    config_exists: Mapped[str] = mapped_column(String(5), nullable=False, default="true")
    project_data_dir: Mapped[str] = mapped_column(Text, nullable=False)
    artifacts_dir: Mapped[str] = mapped_column(Text, nullable=False)
    logs_dir: Mapped[str] = mapped_column(Text, nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_job_id)
    project_name: Mapped[str] = mapped_column(ForeignKey("projects.name"), index=True, nullable=False)
    pipeline: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    config_path: Mapped[str] = mapped_column(Text, nullable=False)
    log_path: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    steps: Mapped[list["JobStep"]] = relationship(
        "JobStep",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobStep.step_order",
    )
    snapshot: Mapped["RunSnapshot | None"] = relationship(
        "RunSnapshot",
        back_populates="job",
        cascade="all, delete-orphan",
        uselist=False,
    )


class JobStep(Base):
    __tablename__ = "job_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_runs.id"), index=True, nullable=False)
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    script_path: Mapped[str] = mapped_column(Text, nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    job: Mapped["JobRun"] = relationship("JobRun", back_populates="steps")


class RunSnapshot(Base):
    __tablename__ = "run_snapshots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_job_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_runs.id"), unique=True, nullable=False)
    project_name: Mapped[str] = mapped_column(ForeignKey("projects.name"), index=True, nullable=False)
    artifacts_dir: Mapped[str] = mapped_column(Text, nullable=False)
    meta_dir: Mapped[str] = mapped_column(Text, nullable=False)
    config_snapshot_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    job: Mapped["JobRun"] = relationship("JobRun", back_populates="snapshot")


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
