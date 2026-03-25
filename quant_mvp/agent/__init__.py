from __future__ import annotations

__all__ = [
    "run_agent_cycle",
    "plan_subagents",
    "sync_subagent_memory",
    "block_subagent",
    "cancel_subagent",
    "retire_subagent",
    "archive_subagent",
    "merge_subagent",
]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(name)
    if name == "run_agent_cycle":
        from .runner import run_agent_cycle

        return run_agent_cycle

    from .subagent_controller import (
        archive_subagent,
        block_subagent,
        cancel_subagent,
        merge_subagent,
        plan_subagents,
        retire_subagent,
        sync_subagent_memory,
    )

    mapping = {
        "plan_subagents": plan_subagents,
        "sync_subagent_memory": sync_subagent_memory,
        "block_subagent": block_subagent,
        "cancel_subagent": cancel_subagent,
        "retire_subagent": retire_subagent,
        "archive_subagent": archive_subagent,
        "merge_subagent": merge_subagent,
    }
    return mapping[name]
