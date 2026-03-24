from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..project import resolve_project_paths
from .ledger import append_jsonl, to_jsonable
from .templates import (
    DOCS_AGENTS_TEMPLATE,
    HYPOTHESIS_QUEUE_TEMPLATE,
    POSTMORTEMS_TEMPLATE,
    PROJECT_STATE_TEMPLATE,
    QUANT_AGENTS_TEMPLATE,
    RESEARCH_MEMORY_TEMPLATE,
    ROOT_AGENTS_TEMPLATE,
    SCRIPTS_AGENTS_TEMPLATE,
    TESTS_AGENTS_TEMPLATE,
)


def _write_if_missing(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def bootstrap_memory_files(project: str, *, repo_root: Path | None = None) -> dict[str, Path]:
    paths = resolve_project_paths(project, root=repo_root)
    repo = paths.root
    _write_if_missing(repo / "AGENTS.md", ROOT_AGENTS_TEMPLATE)
    _write_if_missing(repo / "quant_mvp" / "AGENTS.md", QUANT_AGENTS_TEMPLATE)
    _write_if_missing(repo / "scripts" / "AGENTS.md", SCRIPTS_AGENTS_TEMPLATE)
    _write_if_missing(repo / "tests" / "AGENTS.md", TESTS_AGENTS_TEMPLATE)
    _write_if_missing(repo / "docs" / "AGENTS.md", DOCS_AGENTS_TEMPLATE)

    project_files = {
        "project_state": paths.meta_dir / "PROJECT_STATE.md",
        "hypothesis_queue": paths.meta_dir / "HYPOTHESIS_QUEUE.md",
        "postmortems": paths.meta_dir / "POSTMORTEMS.md",
        "experiment_ledger": paths.meta_dir / "EXPERIMENT_LEDGER.jsonl",
        "research_memory": paths.meta_dir / "RESEARCH_MEMORY.md",
    }
    _write_if_missing(project_files["project_state"], PROJECT_STATE_TEMPLATE.format(project=project))
    _write_if_missing(project_files["hypothesis_queue"], HYPOTHESIS_QUEUE_TEMPLATE)
    _write_if_missing(project_files["postmortems"], POSTMORTEMS_TEMPLATE)
    _write_if_missing(project_files["research_memory"], RESEARCH_MEMORY_TEMPLATE)
    if not project_files["experiment_ledger"].exists():
        project_files["experiment_ledger"].write_text("", encoding="utf-8")
    return project_files


def sync_project_state(project: str, summary: dict[str, Any], *, repo_root: Path | None = None) -> Path:
    files = bootstrap_memory_files(project, repo_root=repo_root)
    lines = ["# Project State", ""]
    for key, value in summary.items():
        if isinstance(value, list):
            lines.append(f"- {key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"- {key}: {value}")
    path = files["project_state"]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def update_hypothesis_queue(project: str, hypotheses: list[str], *, repo_root: Path | None = None) -> Path:
    files = bootstrap_memory_files(project, repo_root=repo_root)
    path = files["hypothesis_queue"]
    lines = ["# Hypothesis Queue", ""]
    for idx, hypothesis in enumerate(hypotheses, start=1):
        lines.append(f"{idx}. {hypothesis}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def record_failure(project: str, entry: dict[str, Any], *, repo_root: Path | None = None) -> Path:
    files = bootstrap_memory_files(project, repo_root=repo_root)
    path = files["postmortems"]
    existing = path.read_text(encoding="utf-8").rstrip()
    block = [
        "",
        f"## {entry.get('timestamp', datetime.utcnow().isoformat())} | {entry.get('experiment_id', 'unknown')}",
        f"- summary: {entry.get('summary', '')}",
        f"- root_cause: {entry.get('root_cause', '')}",
        f"- corrective_action: {entry.get('corrective_action', '')}",
    ]
    path.write_text(existing + "\n" + "\n".join(block).rstrip() + "\n", encoding="utf-8")
    return path


def record_agent_cycle(project: str, payload: dict[str, Any], *, repo_root: Path | None = None) -> dict[str, Path]:
    files = bootstrap_memory_files(project, repo_root=repo_root)
    timestamp = payload.get("timestamp") or datetime.utcnow().isoformat()
    cycle_id = payload.get("cycle_id", "cycle")
    cycle_dir = resolve_project_paths(project, root=repo_root).meta_dir / "agent_cycles"
    cycle_dir.mkdir(parents=True, exist_ok=True)
    cycle_path = cycle_dir / f"{timestamp.replace(':', '').replace('-', '')}_{cycle_id}.json"
    jsonable = to_jsonable(payload)
    cycle_path.write_text(json.dumps(jsonable, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    append_jsonl(files["experiment_ledger"], jsonable)
    return {
        "cycle_path": cycle_path,
        "ledger_path": files["experiment_ledger"],
    }
