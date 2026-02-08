from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .project import resolve_project_paths


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _metrics_markdown(metrics_path: Path) -> str:
    if not metrics_path.exists():
        return "_summary_metrics.csv not found._"
    df = pd.read_csv(metrics_path)
    if df.empty:
        return "_summary_metrics.csv is empty._"
    return _df_markdown(df)


def _df_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "_empty table_"
    cols = [str(c) for c in df.columns]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    lines = [header, sep]
    for _, row in df.iterrows():
        values = [str(row[c]) for c in df.columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def generate_report_markdown(project: str) -> Path:
    paths = resolve_project_paths(project)
    paths.ensure_dirs()

    manifest = _read_json(paths.meta_dir / "run_manifest.json")
    coverage = _read_json(paths.meta_dir / "db_coverage_summary.json")
    report_path = paths.artifacts_dir / "report.md"

    lines: list[str] = []
    lines.append(f"# {project} Report")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(f"- Project: `{project}`")
    lines.append(f"- Generated at: `{manifest.get('generated_at', 'N/A')}`")
    lines.append(f"- Git commit: `{manifest.get('git_commit', 'N/A')}`")
    lines.append(f"- Universe size: `{manifest.get('universe_size', 'N/A')}`")
    lines.append(f"- Rank dates: `{manifest.get('rank_dates', 'N/A')}`")
    lines.append("")
    lines.append("## Backtest Curve")
    lines.append("")
    plot_path = paths.artifacts_dir / "topn_1_5.png"
    if plot_path.exists():
        lines.append("![TopN Equity Curve](topn_1_5.png)")
    else:
        lines.append("_topn_1_5.png not found._")
    lines.append("")
    lines.append("## Summary Metrics")
    lines.append("")
    lines.append(_metrics_markdown(paths.artifacts_dir / "summary_metrics.csv"))
    lines.append("")
    lines.append("## Data Coverage")
    lines.append("")
    if coverage:
        lines.append(f"- universe_size: `{coverage.get('universe_size', coverage.get('n_codes_in_universe', 'N/A'))}`")
        lines.append(f"- db_codes_count: `{coverage.get('db_codes_count', coverage.get('n_codes_in_db', 'N/A'))}`")
        lines.append(f"- median_bars_count: `{coverage.get('median_bars_count', coverage.get('median_bars', 'N/A'))}`")
        lines.append(f"- p10_bars_count: `{coverage.get('p10_bars_count', coverage.get('p10_bars', 'N/A'))}`")
        lines.append(f"- p90_bars_count: `{coverage.get('p90_bars_count', coverage.get('p90_bars', 'N/A'))}`")
        lines.append(f"- min_date: `{coverage.get('min_date', coverage.get('min_first_date', 'N/A'))}`")
        lines.append(f"- max_date: `{coverage.get('max_date', coverage.get('max_last_date', 'N/A'))}`")
        lines.append(f"- coverage_ratio: `{coverage.get('coverage_ratio', 'N/A')}`")
        lines.append(f"- codes_below_min_bars: `{coverage.get('codes_below_min_bars', 'N/A')}`")
        lines.append(f"- backfill_recommendation: `{coverage.get('backfill_recommendation', 'N/A')}`")
    else:
        lines.append("_db_coverage_summary.json not found._")
    lines.append("")

    baselines_path = paths.artifacts_dir / "baseline_metrics.csv"
    if baselines_path.exists():
        lines.append("## Baselines & Random")
        lines.append("")
        lines.append(_df_markdown(pd.read_csv(baselines_path)))
        lines.append("")

    cost_path = paths.artifacts_dir / "cost_sweep_metrics.csv"
    if cost_path.exists():
        lines.append("## Cost Stress Test")
        lines.append("")
        lines.append(_df_markdown(pd.read_csv(cost_path)))
        lines.append("")
        heatmap = paths.artifacts_dir / "cost_sweep_heatmap.png"
        if heatmap.exists():
            lines.append("![Cost Sweep Heatmap](cost_sweep_heatmap.png)")
            lines.append("")

    walk_path = paths.artifacts_dir / "walk_forward_metrics.csv"
    if walk_path.exists():
        lines.append("## Walk-forward")
        lines.append("")
        lines.append(_df_markdown(pd.read_csv(walk_path)))
        lines.append("")
        panel = paths.artifacts_dir / "walk_forward_panel.png"
        if panel.exists():
            lines.append("![Walk-forward Panel](walk_forward_panel.png)")
            lines.append("")

    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return report_path
