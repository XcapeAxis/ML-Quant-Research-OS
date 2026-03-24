from __future__ import annotations

from quant_mvp.agent.runner import run_agent_cycle


def test_agent_cycle_dry_run(limit_up_project) -> None:
    payload = run_agent_cycle(
        project=limit_up_project["project"],
        dry_run=True,
        config_path=limit_up_project["config_path"],
    )
    paths = limit_up_project["paths"]

    assert payload["metadata"]["dry_run"] is True
    assert paths.experiment_ledger_path.exists()
    assert paths.hypothesis_queue_path.exists()
    assert paths.project_state_path.exists()
    assert paths.runtime_cycles_dir.exists()
