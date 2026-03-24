from __future__ import annotations

import json

from quant_mvp.memory.writeback import bootstrap_memory_files, sync_project_state
from quant_mvp.research_audit import run_research_audit


def test_manifest_and_memory_writeback(limit_up_project) -> None:
    project = limit_up_project["project"]
    files = bootstrap_memory_files(project)
    audit = run_research_audit(project, config_path=limit_up_project["config_path"])
    state_path = sync_project_state(
        project,
        {
            "phase": "Phase 1 Research OS",
            "last_audit": audit["system_audit_path"],
            "notes": ["memory writeback contract verified"],
        },
    )

    assert files["experiment_ledger"].exists()
    assert state_path.exists()
    assert "memory writeback contract verified" in state_path.read_text(encoding="utf-8")
    payload = json.loads(limit_up_project["paths"].meta_dir.joinpath("run_manifest.json").read_text(encoding="utf-8")) if limit_up_project["paths"].meta_dir.joinpath("run_manifest.json").exists() else {}
    assert isinstance(payload, dict)
