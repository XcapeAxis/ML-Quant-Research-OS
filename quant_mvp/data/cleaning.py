from __future__ import annotations

from pathlib import Path
from typing import Any

from ..data_quality import rebuild_clean_bars, write_quality_outputs


def clean_project_bars(
    *,
    project: str,
    db_path: Path,
    freq: str,
    codes: list[str],
    meta_dir: Path,
    data_quality_cfg: dict[str, Any] | None,
    full_refresh: bool = False,
) -> dict[str, Any]:
    stats = rebuild_clean_bars(
        db_path=db_path,
        freq=freq,
        codes=codes,
        full_refresh=full_refresh,
        data_quality_cfg=data_quality_cfg,
    )
    summary_path, by_symbol_path = write_quality_outputs(
        project=project,
        freq=freq,
        meta_dir=meta_dir,
        stats=stats,
    )
    stats["summary_path"] = str(summary_path)
    stats["by_symbol_path"] = str(by_symbol_path)
    return stats
