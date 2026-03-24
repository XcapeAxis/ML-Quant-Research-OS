from __future__ import annotations

import json

from quant_mvp.memory.writeback import bootstrap_memory_files, record_agent_cycle


def test_experiment_ledger_append_only(limit_up_project) -> None:
    project = limit_up_project["project"]
    files = bootstrap_memory_files(project)
    ledger_path = files["experiment_ledger"]

    record_agent_cycle(project, {"cycle_id": "first", "timestamp": "2026-03-24T00:00:00", "result": "ok"})
    before = ledger_path.read_text(encoding="utf-8").splitlines()
    record_agent_cycle(project, {"cycle_id": "second", "timestamp": "2026-03-24T00:01:00", "result": "ok"})
    after = ledger_path.read_text(encoding="utf-8").splitlines()

    assert len(after) == len(before) + 1
    assert after[0] == before[0]
    assert json.loads(after[-1])["cycle_id"] == "second"
