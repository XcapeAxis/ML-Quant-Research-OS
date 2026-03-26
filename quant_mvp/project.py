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
    memory_dir: Path
    project_data_dir: Path
    signals_dir: Path
    features_dir: Path
    meta_dir: Path
    artifacts_dir: Path
    logs_dir: Path
    db_path: Path
    universe_path: Path
    pools_dir: Path
    core_pools_dir: Path
    branch_pools_dir: Path
    experiments_dir: Path
    project_state_path: Path
    research_memory_path: Path
    postmortems_path: Path
    hypothesis_queue_path: Path
    experiment_ledger_path: Path
    handoff_path: Path
    migration_prompt_path: Path
    verify_last_path: Path
    session_state_path: Path
    subagent_registry_path: Path
    subagent_ledger_path: Path
    mission_state_path: Path
    branch_ledger_path: Path
    evidence_ledger_path: Path
    portfolio_status_path: Path
    next_round_plan_path: Path
    runtime_cycles_dir: Path
    subagent_artifacts_dir: Path
    automation_runs_dir: Path

    def ensure_dirs(self) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.project_data_dir.mkdir(parents=True, exist_ok=True)
        self.signals_dir.mkdir(parents=True, exist_ok=True)
        self.features_dir.mkdir(parents=True, exist_ok=True)
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.pools_dir.mkdir(parents=True, exist_ok=True)
        self.core_pools_dir.mkdir(parents=True, exist_ok=True)
        self.branch_pools_dir.mkdir(parents=True, exist_ok=True)
        self.experiments_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_cycles_dir.mkdir(parents=True, exist_ok=True)
        self.subagent_artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.automation_runs_dir.mkdir(parents=True, exist_ok=True)


def resolve_project_paths(project: str, root: Path | None = None) -> ProjectPaths:
    repo_root = find_repo_root(root)
    name = validate_project_name(project)
    memory_dir = repo_root / "memory" / "projects" / name
    project_data_dir = repo_root / "data" / "projects" / name
    meta_dir = project_data_dir / "meta"
    pools_dir = meta_dir / "pools"
    return ProjectPaths(
        root=repo_root,
        project=name,
        config_path=repo_root / "configs" / "projects" / f"{name}.json",
        memory_dir=memory_dir,
        project_data_dir=project_data_dir,
        signals_dir=project_data_dir / "signals",
        features_dir=project_data_dir / "features",
        meta_dir=meta_dir,
        artifacts_dir=repo_root / "artifacts" / "projects" / name,
        logs_dir=repo_root / "logs" / "projects" / name,
        db_path=repo_root / "data" / "market.db",
        universe_path=meta_dir / "universe_codes.txt",
        pools_dir=pools_dir,
        core_pools_dir=pools_dir / "core",
        branch_pools_dir=pools_dir / "branch",
        experiments_dir=meta_dir / "experiments",
        project_state_path=memory_dir / "PROJECT_STATE.md",
        research_memory_path=memory_dir / "RESEARCH_MEMORY.md",
        postmortems_path=memory_dir / "POSTMORTEMS.md",
        hypothesis_queue_path=memory_dir / "HYPOTHESIS_QUEUE.md",
        experiment_ledger_path=memory_dir / "EXPERIMENT_LEDGER.jsonl",
        handoff_path=memory_dir / "HANDOFF_NEXT_CHAT.md",
        migration_prompt_path=memory_dir / "MIGRATION_PROMPT_NEXT_CHAT.md",
        verify_last_path=memory_dir / "VERIFY_LAST.md",
        session_state_path=memory_dir / "SESSION_STATE.json",
        subagent_registry_path=memory_dir / "SUBAGENT_REGISTRY.md",
        subagent_ledger_path=memory_dir / "SUBAGENT_LEDGER.jsonl",
        mission_state_path=memory_dir / "MISSION_STATE.json",
        branch_ledger_path=memory_dir / "BRANCH_LEDGER.jsonl",
        evidence_ledger_path=memory_dir / "EVIDENCE_LEDGER.jsonl",
        portfolio_status_path=memory_dir / "PORTFOLIO_STATUS.md",
        next_round_plan_path=memory_dir / "NEXT_ROUND_RESEARCH_PLAN.md",
        runtime_cycles_dir=meta_dir / "agent_cycles",
        subagent_artifacts_dir=(repo_root / "artifacts" / "projects" / name / "subagents"),
        automation_runs_dir=(repo_root / "artifacts" / "projects" / name / "automation_runs"),
    )
