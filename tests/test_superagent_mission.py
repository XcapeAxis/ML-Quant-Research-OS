from __future__ import annotations

import json
from pathlib import Path

from quant_mvp.agent.memory import load_memory_context
from quant_mvp.experiment_graph import read_experiment_record
from quant_mvp.superagent import branch_review, mission_tick


def test_mission_tick_writes_dual_pool_and_branch_ledgers(limit_up_project) -> None:
    payload = mission_tick(
        project=limit_up_project["project"],
        dry_run=True,
        max_branches=3,
        config_path=limit_up_project["config_path"],
    )
    paths = limit_up_project["paths"]

    assert payload["mission_id"].startswith("mission-")
    assert Path(payload["mission_state_path"]).exists()
    assert Path(payload["branch_ledger_path"]).exists()
    assert Path(payload["evidence_ledger_path"]).exists()
    assert Path(payload["portfolio_status_path"]).exists()
    assert Path(payload["core_pool_snapshot_path"]).exists()
    assert payload["branches"]
    assert payload["proposals"]

    mission = json.loads(paths.mission_state_path.read_text(encoding="utf-8"))
    assert mission["mission_id"] == payload["mission_id"]
    assert mission["core_universe_snapshot_id"] == payload["core_pool_snapshot_id"]

    branch_lines = [line for line in paths.branch_ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    evidence_lines = [line for line in paths.evidence_ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(branch_lines) >= 1
    assert len(evidence_lines) >= 1

    latest_bundle = payload["evidence_records"][0]
    tasks_by_role = {item["role"]: item for item in latest_bundle["worker_tasks"]}
    assert tasks_by_role["scout"]["state"] == "verified"
    assert tasks_by_role["scout"]["subagent_id"]
    assert tasks_by_role["scout"]["artifact_refs"]
    assert tasks_by_role["scout"]["started_at"]
    assert tasks_by_role["scout"]["finished_at"]
    assert tasks_by_role["implementer"]["state"] == "verified"
    assert tasks_by_role["implementer"]["subagent_id"]
    assert tasks_by_role["implementer"]["artifact_refs"]
    assert tasks_by_role["implementer"]["started_at"]
    assert tasks_by_role["implementer"]["finished_at"]
    assert tasks_by_role["verifier"]["state"] == "queued"

    session = json.loads(paths.session_state_path.read_text(encoding="utf-8"))
    worker_subagents = [item for item in session["subagents"] if item.get("worker_task_id")]
    assert worker_subagents
    assert any(item["role"] == "scout" and item["status"] == "retired" for item in worker_subagents)
    assert any(item["role"] == "implementer" and item["status"] == "retired" for item in worker_subagents)
    ledger_text = paths.subagent_ledger_path.read_text(encoding="utf-8")
    assert '"action": "spawn_worker"' in ledger_text
    assert '"action": "retire"' in ledger_text

    context = load_memory_context(limit_up_project["project"])
    assert "[mission_state]" in context
    assert "[recent_experiments]" in context
    assert payload["mission_id"] in context


def test_branch_review_promote_runs_one_bounded_verifier(limit_up_project) -> None:
    project = limit_up_project["project"]
    config_path = limit_up_project["config_path"]
    paths = limit_up_project["paths"]

    mission_tick(
        project=project,
        dry_run=True,
        max_branches=3,
        config_path=config_path,
    )
    review_payload = branch_review(
        project=project,
        branch_id="risk_constrained_limit_up",
        action="promote",
    )
    assert review_payload["state"] == "promoted_to_challenger"
    assert review_payload["selected_verifier_branch_id"] == "risk_constrained_limit_up"

    payload = mission_tick(
        project=project,
        dry_run=True,
        max_branches=3,
        config_path=config_path,
    )
    assert payload["selected_verifier_branch_id"] == "risk_constrained_limit_up"

    bundles = {item["branch_id"]: item for item in payload["evidence_records"]}
    risk_bundle = bundles["risk_constrained_limit_up"]
    risk_tasks = {item["role"]: item for item in risk_bundle["worker_tasks"]}
    assert risk_tasks["verifier"]["state"] == "verified"
    assert risk_tasks["verifier"]["subagent_id"]
    assert risk_tasks["verifier"]["artifact_refs"]
    assert risk_bundle["evaluation"]["status"] == "blocked"

    baseline_tasks = {item["role"]: item for item in bundles["baseline_limit_up"]["worker_tasks"]}
    tighter_tasks = {item["role"]: item for item in bundles["tighter_entry_limit_up"]["worker_tasks"]}
    assert baseline_tasks["verifier"]["state"] == "queued"
    assert tighter_tasks["verifier"]["state"] == "queued"

    experiment = read_experiment_record(project, risk_bundle["latest_experiment_id"])
    assert experiment.status == "evaluated"
    assert experiment.factor_candidates
    assert experiment.feature_view is not None
    assert experiment.label_spec is not None
    assert experiment.model_candidate is not None
    assert experiment.model_candidate.is_online_adaptive is False
    assert experiment.regime_spec is not None
    assert experiment.regime_spec.regime_transition_latency is None
    assert experiment.evaluation is not None
    assert experiment.evaluation.classification in {"strategy_quality_failure", "data_or_boundary_failure"}
    assert experiment.evaluation.adversarial_robustness["status"] == "not_evaluated"

    mission = json.loads(paths.mission_state_path.read_text(encoding="utf-8"))
    assert mission["selected_verifier_branch_id"] is None
    assert mission["selected_verifier_consumed_at"]

    ledger_text = paths.experiment_ledger_path.read_text(encoding="utf-8")
    assert risk_bundle["latest_experiment_id"] in ledger_text
    postmortems_text = paths.postmortems_path.read_text(encoding="utf-8")
    assert risk_bundle["latest_experiment_id"] in postmortems_text
