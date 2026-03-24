from __future__ import annotations

from quant_mvp.agent.runner import run_agent_cycle


def test_agent_cycle_dry_run(limit_up_project) -> None:
    payload = run_agent_cycle(
        project=limit_up_project["project"],
        dry_run=True,
        config_path=limit_up_project["config_path"],
    )
    meta_dir = limit_up_project["paths"].meta_dir

    assert payload["metadata"]["dry_run"] is True
    assert (meta_dir / "EXPERIMENT_LEDGER.jsonl").exists()
    assert (meta_dir / "HYPOTHESIS_QUEUE.md").exists()
    assert (meta_dir / "PROJECT_STATE.md").exists()
    assert (meta_dir / "agent_cycles").exists()
