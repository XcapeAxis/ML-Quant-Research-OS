from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_mvp.config import load_config
from quant_mvp.db import coverage_report
from quant_mvp.manifest import update_run_manifest
from quant_mvp.universe import load_universe_codes


def run_audit(project: str, config_path: Path | None = None) -> tuple[Path, Path]:
    cfg, paths = load_config(project, config_path=config_path)
    paths.ensure_dirs()

    universe = load_universe_codes(project)
    db_path = Path(cfg["db_path"])
    df = coverage_report(db_path=db_path, freq=cfg["freq"], codes=universe)
    report_path = paths.meta_dir / "db_coverage_report.csv"
    summary_path = paths.meta_dir / "db_coverage_summary.json"
    df.to_csv(report_path, index=False, encoding="utf-8-sig")

    valid = df[df["bars_count"] > 0].copy()
    universe_size = int(len(universe))
    db_codes_count = int(len(valid))
    min_bars = int(cfg.get("min_bars", 160))
    below_min = int((df["bars_count"] < min_bars).sum())
    coverage_ratio = float(db_codes_count / universe_size) if universe_size > 0 else 0.0

    summary = {
        "project": project,
        "universe_size": universe_size,
        "db_codes_count": db_codes_count,
        "median_bars_count": float(valid["bars_count"].median()) if not valid.empty else 0.0,
        "p10_bars_count": float(valid["bars_count"].quantile(0.1)) if not valid.empty else 0.0,
        "p90_bars_count": float(valid["bars_count"].quantile(0.9)) if not valid.empty else 0.0,
        "min_date": valid["first_date"].min() if not valid.empty else None,
        "max_date": valid["last_date"].max() if not valid.empty else None,
        "codes_below_min_bars": below_min,
        "coverage_ratio": coverage_ratio,
        "backfill_recommendation": (
            "Run backfill; most symbols have insufficient history."
            if below_min > universe_size * 0.2
            else "Coverage looks acceptable for current min_bars threshold."
        ),
        "n_codes_in_universe": universe_size,
        "n_codes_in_db": db_codes_count,
    }
    with open(summary_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)

    update_run_manifest(project, {"db_coverage_stats": summary})
    return report_path, summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit SQLite coverage against frozen universe.")
    parser.add_argument("--project", type=str, default="2026Q1_limit_up")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    report_path, summary_path = run_audit(project=args.project, config_path=args.config)
    print(f"[audit_db] report={report_path}")
    print(f"[audit_db] summary={summary_path}")


if __name__ == "__main__":
    main()
