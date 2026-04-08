from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_mvp.config import load_config
from quant_mvp.db import DataMode, coverage_report, db_date_range, table_row_count
from quant_mvp.manifest import update_run_manifest
from quant_mvp.universe import load_universe_codes


def _coverage_summary(
    *,
    df,
    universe_size: int,
    min_bars: int,
) -> dict[str, float | int | str | None]:
    valid = df[df["bars_count"] > 0].copy()
    db_codes_count = int(len(valid))
    below_min = int((df["bars_count"] < min_bars).sum())
    coverage_ratio = float(db_codes_count / universe_size) if universe_size > 0 else 0.0
    return {
        "db_codes_count": db_codes_count,
        "median_bars_count": float(valid["bars_count"].median()) if not valid.empty else 0.0,
        "p10_bars_count": float(valid["bars_count"].quantile(0.1)) if not valid.empty else 0.0,
        "p90_bars_count": float(valid["bars_count"].quantile(0.9)) if not valid.empty else 0.0,
        "min_date": valid["first_date"].min() if not valid.empty else None,
        "max_date": valid["last_date"].max() if not valid.empty else None,
        "codes_below_min_bars": below_min,
        "coverage_ratio": coverage_ratio,
    }


def run_audit(
    project: str,
    config_path: Path | None = None,
    data_mode: DataMode = "clean",
) -> tuple[Path, Path]:
    cfg, paths = load_config(project, config_path=config_path)
    paths.ensure_dirs()

    universe = load_universe_codes(project)
    db_path = Path(cfg["db_path"])
    freq = str(cfg["freq"])
    df = coverage_report(db_path=db_path, freq=freq, codes=universe, data_mode=data_mode)
    raw_df = coverage_report(db_path=db_path, freq=freq, codes=universe, data_mode="raw")
    clean_df = coverage_report(db_path=db_path, freq=freq, codes=universe, data_mode="clean")
    report_path = paths.meta_dir / "db_coverage_report.csv"
    summary_path = paths.meta_dir / "db_coverage_summary.json"
    df.to_csv(report_path, index=False, encoding="utf-8-sig")

    universe_size = int(len(universe))
    min_bars = int(cfg.get("min_bars", 160))
    selected_summary = _coverage_summary(df=df, universe_size=universe_size, min_bars=min_bars)
    raw_summary = _coverage_summary(df=raw_df, universe_size=universe_size, min_bars=min_bars)
    clean_summary = _coverage_summary(df=clean_df, universe_size=universe_size, min_bars=min_bars)

    summary = {
        "project": project,
        "data_mode": data_mode,
        "universe_size": universe_size,
        "db_codes_count": selected_summary["db_codes_count"],
        "median_bars_count": selected_summary["median_bars_count"],
        "p10_bars_count": selected_summary["p10_bars_count"],
        "p90_bars_count": selected_summary["p90_bars_count"],
        "min_date": selected_summary["min_date"],
        "max_date": selected_summary["max_date"],
        "codes_below_min_bars": selected_summary["codes_below_min_bars"],
        "coverage_ratio": selected_summary["coverage_ratio"],
        "raw_db_codes_count": raw_summary["db_codes_count"],
        "raw_coverage_ratio": raw_summary["coverage_ratio"],
        "clean_db_codes_count": clean_summary["db_codes_count"],
        "clean_coverage_ratio": clean_summary["coverage_ratio"],
        "raw_rows_total": table_row_count(db_path, "bars", freq=freq),
        "clean_rows_total": table_row_count(db_path, "bars_clean", freq=freq),
        "raw_date_range": {
            "min": db_date_range(db_path, freq=freq, data_mode="raw")[0],
            "max": db_date_range(db_path, freq=freq, data_mode="raw")[1],
        },
        "clean_date_range": {
            "min": db_date_range(db_path, freq=freq, data_mode="clean")[0],
            "max": db_date_range(db_path, freq=freq, data_mode="clean")[1],
        },
        "backfill_recommendation": (
            "Run backfill; most symbols have insufficient history."
            if selected_summary["codes_below_min_bars"] > universe_size * 0.2
            else "Coverage looks acceptable for current min_bars threshold."
        ),
        "n_codes_in_universe": universe_size,
        "n_codes_in_db": selected_summary["db_codes_count"],
    }
    with open(summary_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)

    update_run_manifest(project, {"db_coverage_stats": summary})
    return report_path, summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit SQLite coverage against frozen universe.")
    parser.add_argument("--project", type=str, default="crypto_okx_research_v1")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--data-mode", type=str, default="clean", choices=["auto", "clean", "raw"])
    args = parser.parse_args()

    report_path, summary_path = run_audit(
        project=args.project,
        config_path=args.config,
        data_mode=args.data_mode,
    )
    print(f"[audit_db] report={report_path}")
    print(f"[audit_db] summary={summary_path}")


if __name__ == "__main__":
    main()
