from __future__ import annotations

from quant_mvp.memory.writeback import bootstrap_memory_files, write_verify_snapshot


def test_verify_last_writes_latest_summary(limit_up_project) -> None:
    project = limit_up_project["project"]
    paths = limit_up_project["paths"]
    bootstrap_memory_files(project)
    verify_path = write_verify_snapshot(
        project,
        {
            "passed_commands": ["python -m pytest tests -q"],
            "failed_commands": ["python -m quant_mvp promote_candidate --project test_limit_up_project"],
            "default_project_data_status": "synthetic fixture has validated bars",
            "conclusion_boundary_engineering": "engineering automation works in fixture tests",
            "conclusion_boundary_research": "synthetic fixture only",
            "last_verified_capability": "verify snapshot writeback works",
        },
    )

    text = verify_path.read_text(encoding="utf-8")
    assert verify_path == paths.verify_last_path
    assert "python -m pytest tests -q" in text
    assert "synthetic fixture has validated bars" in text
    assert "engineering automation works in fixture tests" in text
    assert "subagent_gate_mode: AUTO" in text
    assert "当前主线策略" in text
    assert "当前轮次类型" in text
