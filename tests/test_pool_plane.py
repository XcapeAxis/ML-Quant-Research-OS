from __future__ import annotations

from quant_mvp.pools import build_branch_pool_snapshot, build_core_universe_snapshot, explain_pool_membership


def test_core_pool_explains_missing_metadata_without_silent_filtering(limit_up_project) -> None:
    build = build_core_universe_snapshot(
        project=limit_up_project["project"],
        config_path=limit_up_project["config_path"],
    )
    snapshot, path = build
    explanation = explain_pool_membership(
        project=limit_up_project["project"],
        code=limit_up_project["universe_codes"][0],
        kind="core",
    )

    assert path.exists()
    assert snapshot.snapshot_id.startswith("core-")
    assert explanation.snapshot_id == snapshot.snapshot_id
    assert any("unavailable" in reason for reason in explanation.reasons + explanation.notes)


def test_branch_pool_is_derived_from_core_pool(limit_up_project) -> None:
    core_snapshot, _ = build_core_universe_snapshot(
        project=limit_up_project["project"],
        config_path=limit_up_project["config_path"],
    )
    branch_snapshot, path = build_branch_pool_snapshot(
        project=limit_up_project["project"],
        branch_id="limit_up_reaccumulation_baseline",
        hypothesis="baseline branch",
        config_path=limit_up_project["config_path"],
        core_snapshot=core_snapshot,
    )
    explanation = explain_pool_membership(
        project=limit_up_project["project"],
        code=limit_up_project["universe_codes"][0],
        kind="branch",
        branch_id="limit_up_reaccumulation_baseline",
    )

    assert path.exists()
    assert branch_snapshot.core_snapshot_id == core_snapshot.snapshot_id
    assert set(branch_snapshot.codes).issubset(set(core_snapshot.codes))
    assert explanation.snapshot_id == branch_snapshot.snapshot_id
