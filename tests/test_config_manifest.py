from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from quant_mvp.config import load_config
from quant_mvp.manifest import update_run_manifest
from quant_mvp.ranking import build_momentum_rank


def test_config_merge_priority(tmp_path: Path) -> None:
    config_path = tmp_path / "cfg.json"
    config_path.write_text(
        """
{
  "lookback": 10,
  "baselines": {
    "random_trials": 50
  }
}
        """,
        encoding="utf-8",
    )
    cfg, _ = load_config(
        project="2026Q1_limit_up",
        config_path=config_path,
        overrides={"lookback": 30, "baselines": {"random_trials": 10}},
    )
    assert cfg["lookback"] == 30
    assert cfg["baselines"]["random_trials"] == 10
    assert "topk" in cfg


def test_rank_respects_universe(synthetic_project) -> None:
    ctx = synthetic_project
    result = build_momentum_rank(
        db_path=ctx["db_path"],
        freq="1d",
        universe_codes=ctx["universe_codes"],
        lookback=5,
        rebalance_every=5,
        topk=5,
        min_bars=20,
        max_codes_scan=100,
    )
    codes = set(result.rank_df["code"].unique().tolist())
    assert "999999" not in codes
    assert codes.issubset(set(ctx["universe_codes"]))


def test_candidate_count_correctness(synthetic_project) -> None:
    ctx = synthetic_project
    result = build_momentum_rank(
        db_path=ctx["db_path"],
        freq="1d",
        universe_codes=ctx["universe_codes"],
        lookback=5,
        rebalance_every=1,
        topk=5,
        min_bars=20,
        max_codes_scan=100,
    )
    candidate_counts = result.candidate_count_df.set_index("date")["candidate_count"]
    expected = (
        result.candidate_scores_df.groupby("date")["code"]
        .count()
        .reindex(candidate_counts.index)
        .fillna(0)
        .astype(int)
    )
    pd.testing.assert_series_equal(candidate_counts.astype(int), expected, check_names=False)


def test_manifest_completeness(synthetic_project) -> None:
    ctx = synthetic_project
    manifest_path = update_run_manifest(
        ctx["project"],
        {
            "rank_dates": 12,
            "candidate_count_stats": {"min": 1.0, "median": 2.0, "p10": 1.0},
        },
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key in ["project", "generated_at", "git_commit", "universe_size", "rank_dates", "candidate_count_stats"]:
        assert key in payload
