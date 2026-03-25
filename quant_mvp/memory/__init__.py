from __future__ import annotations

from .ledger import append_jsonl, stable_hash

__all__ = [
    "append_jsonl",
    "stable_hash",
    "bootstrap_memory_files",
    "generate_handoff",
    "load_machine_state",
    "record_agent_cycle",
    "record_experiment_result",
    "record_failure",
    "save_machine_state",
    "sync_research_memory",
    "sync_project_state",
    "update_hypothesis_queue",
    "write_verify_snapshot",
]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(name)
    if name in {"append_jsonl", "stable_hash"}:
        return globals()[name]

    from . import writeback as _writeback

    return getattr(_writeback, name)
