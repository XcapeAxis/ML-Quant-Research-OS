from __future__ import annotations

from quant_mvp.data.cleaning import clean_project_bars
from quant_mvp.data.validation import validate_project_data
from quant_mvp.memory.writeback import bootstrap_memory_files, load_machine_state, sync_research_memory, write_verify_snapshot


def test_validate_project_data_reports_non_zero_coverage(limit_up_project) -> None:
    ctx = limit_up_project
    clean_project_bars(
        project=ctx["project"],
        db_path=ctx["db_path"],
        freq="1d",
        codes=ctx["universe_codes"],
        meta_dir=ctx["paths"].meta_dir,
        data_quality_cfg={"enabled": True},
        full_refresh=True,
    )

    report = validate_project_data(
        project=ctx["project"],
        db_path=ctx["db_path"],
        freq="1d",
        universe_codes=ctx["universe_codes"],
        provider_name="akshare",
        data_quality_cfg={"source_table": "bars", "clean_table": "bars_clean"},
        limit_threshold=0.095,
    )

    assert report.coverage_ratio > 0.0
    assert report.raw_rows > 0
    assert report.cleaned_rows > 0
    assert report.validated_rows > 0


def test_verify_snapshot_captures_real_input_boundaries(limit_up_project) -> None:
    verify_path = write_verify_snapshot(
        limit_up_project["project"],
        {
            "passed_commands": ["python -m quant_mvp data_validate --project test_limit_up_project"],
            "failed_commands": [],
            "default_project_data_status": "pilot bars restored for a non-zero subset",
            "conclusion_boundary_engineering": "real-input validation path now executes",
            "conclusion_boundary_research": "coverage is non-zero but still partial",
            "last_verified_capability": "verify snapshot writes real-input boundaries",
        },
    )

    text = verify_path.read_text(encoding="utf-8")
    assert "pilot bars restored for a non-zero subset" in text
    assert "real-input validation path now executes" in text
    assert "coverage is non-zero but still partial" in text


def test_memory_package_exports_are_lazy_import_safe() -> None:
    from quant_mvp.agent import plan_subagents
    from quant_mvp.memory import stable_hash, write_verify_snapshot as exported_write_verify_snapshot

    assert callable(plan_subagents)
    assert callable(exported_write_verify_snapshot)
    assert isinstance(stable_hash({"ok": True}), str)


def test_tracked_research_memory_wins_over_legacy_runtime_copy(limit_up_project) -> None:
    project = limit_up_project["project"]
    paths = limit_up_project["paths"]
    bootstrap_memory_files(project)
    sync_research_memory(
        project,
        durable_facts=["tracked fact"],
        negative_memory=["tracked negative"],
        next_step_memory=["tracked next"],
    )

    legacy_path = paths.meta_dir / "RESEARCH_MEMORY.md"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text(
        "# Research Memory\n\n## Durable Facts\n- legacy fact\n\n## Negative Memory\n- legacy negative\n\n## Next-Step Memory\n- legacy next\n",
        encoding="utf-8",
    )

    _, state = load_machine_state(project)

    assert state["durable_facts"] == ["tracked fact"]
    assert state["negative_memory"] == ["tracked negative"]
    assert state["next_step_memory"] == ["tracked next"]
