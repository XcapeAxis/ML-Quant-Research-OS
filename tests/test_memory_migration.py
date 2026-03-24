from __future__ import annotations

import json

from quant_mvp.memory.writeback import bootstrap_memory_files


def test_memory_bootstrap_migrates_legacy_runtime_memory(limit_up_project) -> None:
    paths = limit_up_project["paths"]

    paths.meta_dir.mkdir(parents=True, exist_ok=True)
    (paths.meta_dir / "PROJECT_STATE.md").write_text(
        "\n".join(
            [
                "# Project State",
                "",
                "- phase: Legacy Phase",
                "- data_status: legacy blocker from runtime memory",
                "- next_priority:",
                "  - recover tracked memory from ignored runtime files",
                "- last_agent_cycle: legacy dry-run failed",
            ],
        ),
        encoding="utf-8",
    )
    (paths.meta_dir / "RESEARCH_MEMORY.md").write_text(
        "\n".join(
            [
                "# Research Memory",
                "",
                "- Durable facts:",
                "  - legacy durable fact",
                "- Negative memory:",
                "  - legacy negative memory",
                "- Next-step memory:",
                "  - legacy next step",
            ],
        ),
        encoding="utf-8",
    )
    (paths.meta_dir / "POSTMORTEMS.md").write_text(
        "\n".join(
            [
                "# Postmortems",
                "",
                "## 2026-03-25T00:00:00+00:00 | legacy-cycle",
                "- summary: legacy failure summary",
                "- root_cause: legacy root cause",
                "- corrective_action: legacy corrective action",
                "- resolution_status: not_fixed",
            ],
        ),
        encoding="utf-8",
    )
    (paths.meta_dir / "HYPOTHESIS_QUEUE.md").write_text(
        "# Hypothesis Queue\n\n1. [blocked] legacy hypothesis\n",
        encoding="utf-8",
    )
    (paths.meta_dir / "EXPERIMENT_LEDGER.jsonl").write_text(
        json.dumps(
            {
                "cycle_id": "legacy-cycle",
                "timestamp": "2026-03-25T00:00:00+00:00",
                "metadata": {"project": limit_up_project["project"], "config_hash": "legacy-hash"},
                "plan": {"primary_hypothesis": "legacy hypothesis"},
                "evaluation": {
                    "passed": False,
                    "promotion_decision": {"reasons": ["legacy blocker"]},
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    files = bootstrap_memory_files(limit_up_project["project"])

    assert "legacy durable fact" in files["research_memory"].read_text(encoding="utf-8")
    assert "legacy negative memory" in files["research_memory"].read_text(encoding="utf-8")
    assert "legacy next step" in files["research_memory"].read_text(encoding="utf-8")
    assert "legacy hypothesis" in files["hypothesis_queue"].read_text(encoding="utf-8")
    assert "legacy failure summary" in files["postmortems"].read_text(encoding="utf-8")
    assert "legacy root cause" in files["project_state"].read_text(encoding="utf-8")

    ledger_lines = files["experiment_ledger"].read_text(encoding="utf-8").splitlines()
    assert len(ledger_lines) == 1
    compact = json.loads(ledger_lines[0])
    assert compact["experiment_id"] == "legacy-cycle"
    assert compact["config_hash"] == "legacy-hash"
    assert compact["result"] == "blocked"
    assert compact["blockers"] == ["legacy blocker"]
