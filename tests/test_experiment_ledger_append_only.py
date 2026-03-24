from __future__ import annotations

import json

from quant_mvp.memory.writeback import bootstrap_memory_files, record_experiment_result


def test_experiment_ledger_append_only(limit_up_project) -> None:
    project = limit_up_project["project"]
    files = bootstrap_memory_files(project)
    ledger_path = files["experiment_ledger"]

    record_experiment_result(
        project,
        {
            "timestamp": "2026-03-24T00:00:00",
            "experiment_id": "first",
            "result": "ok",
            "blockers": [],
            "artifact_refs": [],
        },
    )
    before = ledger_path.read_text(encoding="utf-8").splitlines()
    record_experiment_result(
        project,
        {
            "timestamp": "2026-03-24T00:01:00",
            "experiment_id": "second",
            "result": "ok",
            "blockers": [],
            "artifact_refs": [],
        },
    )
    after = ledger_path.read_text(encoding="utf-8").splitlines()

    assert len(after) == len(before) + 1
    assert after[0] == before[0]
    assert json.loads(after[-1])["experiment_id"] == "second"
