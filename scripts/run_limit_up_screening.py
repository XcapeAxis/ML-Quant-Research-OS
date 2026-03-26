"""Run the audited limit-up screening pipeline end-to-end."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_mvp.config import load_config
from quant_mvp.manifest import update_run_manifest
from quant_mvp.pools import resolve_research_universe_codes
from quant_mvp.research_core import build_limit_up_rank_artifacts, run_limit_up_backtest_artifacts
from quant_mvp.universe import load_universe_codes


def _load_strategy_universe(project: str, config_path: Path | None) -> list[str]:
    try:
        return load_universe_codes(project)
    except FileNotFoundError:
        universe, _ = resolve_research_universe_codes(
            project,
            config_path=config_path,
            build_if_missing=True,
        )
        return universe


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the audited limit-up screening strategy.")
    parser.add_argument("--project", type=str, default="as_share_research_v1")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--save", type=str, default="auto")
    parser.add_argument("--no-show", action="store_true")
    args = parser.parse_args()

    cfg, paths = load_config(args.project, config_path=args.config)
    paths.ensure_dirs()

    universe = _load_strategy_universe(args.project, args.config)
    rank_artifacts = build_limit_up_rank_artifacts(
        cfg=cfg,
        paths=paths,
        universe_codes=universe,
    )
    backtest_artifacts = run_limit_up_backtest_artifacts(
        cfg=cfg,
        paths=paths,
        rank_df=rank_artifacts.selection.rank_df,
        save=args.save,
        no_show=args.no_show,
    )

    manifest_updates = dict(rank_artifacts.manifest_updates)
    manifest_updates.update(backtest_artifacts.manifest_updates)
    update_run_manifest(
        args.project,
        manifest_updates,
    )

    print(f"[limit_up_screening] project={args.project} metrics={backtest_artifacts.metrics_path}")
    if backtest_artifacts.plot_path:
        print(f"[limit_up_screening] plot={backtest_artifacts.plot_path}")


if __name__ == "__main__":
    main()
