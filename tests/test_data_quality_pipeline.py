from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd

from quant_mvp.db import load_close_volume_panel, table_row_count, upsert_bars


def _load_script_module(module_name: str, rel_path: str):
    root = Path(__file__).resolve().parents[1]
    path = root / rel_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_update_bars_auto_triggers_cleaning(monkeypatch, synthetic_project) -> None:
    step11 = _load_script_module("step11_clean_test", "scripts/steps/11_update_bars.py")
    ctx = synthetic_project

    def _fake_fetch(
        *,
        code: str,
        start_yyyymmdd: str,
        end_yyyymmdd: str,
        freq: str,
        timeout_seconds: float,
    ) -> pd.DataFrame:
        del start_yyyymmdd, end_yyyymmdd, timeout_seconds
        return pd.DataFrame(
            [
                {
                    "symbol": str(code).zfill(6),
                    "datetime": "2020-07-01",
                    "freq": freq,
                    "open": 12.0,
                    "high": 12.2,
                    "low": 11.9,
                    "close": 12.1,
                    "volume": 1500.0,
                },
                {
                    "symbol": str(code).zfill(6),
                    "datetime": "2020-07-02",
                    "freq": freq,
                    "open": 12.1,
                    "high": 12.3,
                    "low": 12.0,
                    "close": 12.2,
                    "volume": 0.0,
                },
            ],
        )

    monkeypatch.setattr(step11, "_fetch_akshare_daily", _fake_fetch)

    stats = step11.run_update(
        project=ctx["project"],
        mode="backfill",
        freq="1d",
        start_date="20200701",
        end_date="20200702",
        workers=1,
        max_codes_scan=1,
        db_path=ctx["db_path"],
        data_quality_cfg={"enabled": True, "auto_clean_after_update": True},
    )

    assert stats["updated_codes"] == 1
    assert "data_quality" in stats
    assert stats["data_quality"]["clean_rows"] > 0
    assert table_row_count(ctx["db_path"], "bars_clean", freq="1d") > 0
    assert table_row_count(ctx["db_path"], "bar_issues", freq="1d") > 0

    meta_dir = ctx["paths"].meta_dir
    summary_path = meta_dir / "data_quality_summary.json"
    assert summary_path.exists()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["clean_rows"] > 0


def test_clean_command_and_auto_mode_use_clean_table(synthetic_project) -> None:
    ctx = synthetic_project

    # Introduce a raw hard-anomaly row that should be removed from bars_clean.
    dirty = pd.DataFrame(
        [
            {
                "symbol": "000001",
                "datetime": "2020-06-17",
                "freq": "1d",
                "open": 50.0,
                "high": 50.5,
                "low": 49.5,
                "close": 50.0,
                "volume": 2000.0,
            },
        ],
    )
    upsert_bars(ctx["db_path"], dirty)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/steps/12_clean_bars.py",
            "--project",
            ctx["project"],
            "--config",
            str(ctx["config_path"]),
            "--full-refresh",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(f"clean command failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

    close, _ = load_close_volume_panel(ctx["db_path"], "1d", ["000001"], data_mode="auto")
    assert close.index.max().strftime("%Y-%m-%d") == "2020-06-16"
