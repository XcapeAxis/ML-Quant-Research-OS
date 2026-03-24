from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from quant_mvp.config import load_config
from quant_mvp.data_quality import clean_table_ready, rebuild_clean_bars, write_quality_outputs
from quant_mvp.db import coverage_report, db_date_range, list_db_codes
from quant_mvp.manifest import update_run_manifest
from quant_mvp.project import resolve_project_paths


ScriptRunner = Callable[[str, tuple[str, ...]], int]
LogWriter = Callable[[str], None]
PREPARATION_STATUS_FILENAME = "prepare_data_status.json"


@dataclass(frozen=True)
class PreparationDecision:
    action: str
    reason: str
    rebuild_clean_only: bool = False
    decision_key: str = "skip"
    trace: list[dict[str, Any]] = field(default_factory=list)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _trace_entry(stage: str, message: str, **detail: Any) -> dict[str, Any]:
    return {"stage": stage, "message": message, "detail": detail}


def _clean_table_name(cfg: dict) -> str:
    return str(cfg.get("data_quality", {}).get("clean_table", "bars_clean"))


def _has_nonempty_universe(universe_path: Path) -> bool:
    if not universe_path.exists():
        return False
    with open(universe_path, "r", encoding="utf-8") as handle:
        return any(line.strip() for line in handle)


def _load_universe_codes(universe_path: Path) -> list[str]:
    with open(universe_path, "r", encoding="utf-8") as handle:
        return sorted({line.strip() for line in handle if line.strip()})


def _has_historical_gap(
    *,
    raw_full,
    raw_window,
    start_date: str | None,
    end_date: str,
) -> bool:
    merged = raw_full.merge(raw_window, on="code", how="left", suffixes=("_full", "_window"))
    if merged.empty:
        return False

    start_text = str(start_date or end_date)
    window_count = merged["bars_count_window"].fillna(0)
    window_first = merged["first_date_window"].fillna("9999-12-31")
    window_last = merged["last_date_window"].fillna("")

    return bool(
        (
            (merged["bars_count_full"] > 0)
            & merged["first_date_full"].fillna("9999-12-31").le(str(end_date))
            & merged["last_date_full"].fillna("").ge(start_text)
            & ((window_count == 0) | window_first.gt(start_text) | window_last.lt(str(end_date)))
        ).any()
    )


def ensure_project_universe(
    *,
    project: str,
    config_path: Path,
    repo_root: Path,
    script_runner: ScriptRunner,
    log: LogWriter,
) -> None:
    del config_path
    paths = resolve_project_paths(project, root=repo_root)
    if _has_nonempty_universe(paths.universe_path):
        log("检测到股票池文件已存在，跳过自动构建。")
        return

    log("检测到股票池缺失，正在自动构建。")
    exit_code = script_runner("scripts/steps/10_symbols.py", ())
    if exit_code != 0 or not _has_nonempty_universe(paths.universe_path):
        raise RuntimeError("自动构建股票池失败，请检查外部行情库、代理配置或远程数据源。")
    log("股票池构建完成。")


def determine_preparation_decision(
    *,
    project: str,
    config_path: Path,
    repo_root: Path,
) -> PreparationDecision:
    del repo_root
    cfg, paths = load_config(project, config_path=config_path)
    freq = str(cfg["freq"])
    db_path = Path(cfg["db_path"])
    start_date = cfg.get("start_date")
    end_date = cfg.get("end_date")
    clean_table = _clean_table_name(cfg)
    trace: list[dict[str, Any]] = [
        _trace_entry("inputs", "已载入项目配置。", freq=freq, start_date=start_date, end_date=end_date),
    ]

    if not _has_nonempty_universe(paths.universe_path):
        trace.append(_trace_entry("universe", "检测到股票池缺失。", universe_path=str(paths.universe_path)))
        return PreparationDecision(
            action="build_universe",
            decision_key="build_universe",
            reason="检测到股票池缺失，需要先构建股票池。",
            trace=trace,
        )

    trace.append(_trace_entry("universe", "股票池已存在。", universe_path=str(paths.universe_path)))

    if end_date in (None, ""):
        trace.append(_trace_entry("decision", "end_date 为空，按增量更新处理。"))
        return PreparationDecision(
            action="incremental",
            decision_key="incremental",
            reason="检测到回测结束日期为空，正在执行增量更新以补齐最新尾部数据。",
            trace=trace,
        )

    raw_min, raw_max = db_date_range(db_path, freq=freq, data_mode="raw")
    trace.append(_trace_entry("raw_range", "已检查原始行情日期范围。", raw_min=raw_min, raw_max=raw_max))
    if raw_min is None or raw_max is None:
        trace.append(_trace_entry("decision", "原始行情库为空，需要执行回补。"))
        return PreparationDecision(
            action="backfill",
            decision_key="backfill",
            reason="检测到原始行情库为空，正在按目标回测区间执行回补。",
            trace=trace,
        )

    if start_date and str(raw_min) > str(start_date):
        trace.append(
            _trace_entry(
                "decision",
                "原始行情起始日期晚于目标窗口起点，需要执行回补。",
                raw_min=raw_min,
                target_start=start_date,
            )
        )
        return PreparationDecision(
            action="backfill",
            decision_key="backfill",
            reason="检测到数据库起始日期晚于目标回测起点，正在执行回补。",
            trace=trace,
        )

    universe_codes = _load_universe_codes(paths.universe_path)
    raw_window = coverage_report(
        db_path=db_path,
        freq=freq,
        codes=universe_codes,
        data_mode="raw",
        start=str(start_date) if start_date else None,
        end=str(end_date),
    )
    raw_full = coverage_report(
        db_path=db_path,
        freq=freq,
        codes=universe_codes,
        data_mode="raw",
    )
    trace.append(
        _trace_entry(
            "coverage",
            "已检查原始行情覆盖。",
            expected_codes=len(universe_codes),
            raw_codes_with_window=int((raw_window["bars_count"] > 0).sum()) if not raw_window.empty else 0,
        )
    )

    if _has_historical_gap(
        raw_full=raw_full,
        raw_window=raw_window,
        start_date=str(start_date) if start_date else None,
        end_date=str(end_date),
    ):
        trace.append(_trace_entry("decision", "目标窗口存在历史缺口，需要执行回补。"))
        return PreparationDecision(
            action="backfill",
            decision_key="backfill",
            reason="检测到回测区间历史数据不足，正在执行回补。",
            trace=trace,
        )

    if str(raw_max) < str(end_date):
        trace.append(
            _trace_entry(
                "decision",
                "原始行情最新日期早于目标结束日期，需要执行增量更新。",
                raw_max=raw_max,
                target_end=end_date,
            )
        )
        return PreparationDecision(
            action="incremental",
            decision_key="incremental",
            reason="检测到最新尾部数据未覆盖到目标结束日期，正在执行增量更新。",
            trace=trace,
        )

    if not clean_table_ready(db_path, freq=freq, clean_table=clean_table, codes=universe_codes):
        trace.append(_trace_entry("decision", "清洗表缺失，仅重建 clean 结果。", clean_table=clean_table))
        return PreparationDecision(
            action="none",
            decision_key="clean_only",
            reason="检测到清洗表缺失，正在基于现有原始数据重建清洗结果。",
            rebuild_clean_only=True,
            trace=trace,
        )

    trace.append(_trace_entry("decision", "当前覆盖充足，无需补数。"))
    return PreparationDecision(
        action="none",
        decision_key="skip",
        reason="检测到目标回测区间数据覆盖充足，无需补数。",
        trace=trace,
    )


def _rebuild_clean_outputs(
    *,
    project: str,
    config_path: Path,
    log: LogWriter,
) -> dict[str, Any]:
    cfg, paths = load_config(project, config_path=config_path)
    db_path = Path(cfg["db_path"])
    freq = str(cfg["freq"])
    codes = sorted(list_db_codes(db_path, freq=freq, data_mode="raw"))
    if not codes:
        raise RuntimeError("原始行情库中没有可供清洗的数据，任务终止。")

    log("行情更新完成，正在执行数据清洗。")
    stats = rebuild_clean_bars(
        db_path=db_path,
        freq=freq,
        codes=codes,
        full_refresh=True,
        data_quality_cfg=cfg.get("data_quality"),
    )
    summary_path, by_symbol_path = write_quality_outputs(
        project=project,
        freq=freq,
        meta_dir=paths.meta_dir,
        stats=stats,
    )
    update_run_manifest(
        project,
        {
            "data_quality": {
                "summary_path": str(summary_path),
                "by_symbol_path": str(by_symbol_path),
                "clean_rows": stats.get("clean_rows", 0),
                "source_rows": stats.get("source_rows", 0),
            },
        },
    )
    return {
        "summary_path": str(summary_path),
        "by_symbol_path": str(by_symbol_path),
        "clean_rows": stats.get("clean_rows", 0),
        "source_rows": stats.get("source_rows", 0),
    }


def _validate_clean_coverage(
    *,
    project: str,
    config_path: Path,
) -> dict[str, Any]:
    cfg, paths = load_config(project, config_path=config_path)
    db_path = Path(cfg["db_path"])
    freq = str(cfg["freq"])
    clean_table = _clean_table_name(cfg)
    universe_codes = _load_universe_codes(paths.universe_path)
    if not clean_table_ready(db_path, freq=freq, clean_table=clean_table, codes=universe_codes):
        raise RuntimeError("清洗后未生成可用的 clean 数据，任务终止。")

    end_date = cfg.get("end_date")
    start_date = cfg.get("start_date")
    if end_date in (None, ""):
        return {
            "enabled": False,
            "reason": "end_date_missing",
        }

    clean_window = coverage_report(
        db_path=db_path,
        freq=freq,
        codes=universe_codes,
        data_mode="clean",
        start=str(start_date) if start_date else None,
        end=str(end_date),
    )
    if clean_window.empty or int((clean_window["bars_count"] > 0).sum()) == 0:
        raise RuntimeError("清洗后目标回测区间仍无可用数据，任务终止。")

    return {
        "enabled": True,
        "window_start": str(start_date) if start_date else None,
        "window_end": str(end_date),
        "clean_codes_with_data": int((clean_window["bars_count"] > 0).sum()),
        "clean_rows_in_window": int(clean_window["bars_count"].sum()),
    }


def _read_audit_summary(summary_path: Path) -> dict[str, Any]:
    if not summary_path.exists():
        return {}
    with open(summary_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_preparation_status(project: str, payload: dict[str, Any]) -> Path:
    paths = resolve_project_paths(project)
    status_path = paths.meta_dir / PREPARATION_STATUS_FILENAME
    _write_json(status_path, payload)
    return status_path


def prepare_project_data(
    *,
    project: str,
    config_path: Path,
    repo_root: Path,
    script_runner: ScriptRunner,
    log: LogWriter,
) -> PreparationDecision:
    decision = determine_preparation_decision(project=project, config_path=config_path, repo_root=repo_root)
    if decision.action == "build_universe":
        raise RuntimeError("股票池尚未准备完成，无法开始数据预处理。")

    cfg, paths = load_config(project, config_path=config_path)
    end_date = cfg.get("end_date")
    start_date = cfg.get("start_date")
    clean_summary: dict[str, Any] | None = None
    update_payload: dict[str, Any] | None = None
    audit_summary: dict[str, Any] = {}

    summary_payload: dict[str, Any] = {
        "generated_at": _utc_now_iso(),
        "status": "running",
        "decision": decision.decision_key,
        "reason": decision.reason,
        "decision_trace": decision.trace,
        "project": project,
        "config_path": str(config_path),
    }

    try:
        log(decision.reason)
        if decision.action in {"incremental", "backfill"}:
            extra_args: list[str] = ["--mode", decision.action]
            if decision.action == "backfill":
                if start_date:
                    extra_args.extend(["--start-date", str(start_date)])
                if end_date:
                    extra_args.extend(["--end-date", str(end_date)])
            summary_payload["update_request"] = {
                "mode": decision.action,
                "start_date": str(start_date) if start_date else None,
                "end_date": str(end_date) if end_date else None,
            }
            exit_code = script_runner("scripts/steps/11_update_bars.py", tuple(extra_args))
            if exit_code != 0:
                raise RuntimeError("目标回测区间数据缺失，自动补数失败，请检查网络、代理或数据源。")
            update_payload = summary_payload["update_request"]
        elif decision.rebuild_clean_only:
            clean_summary = _rebuild_clean_outputs(project=project, config_path=config_path, log=log)
        else:
            log("数据覆盖满足当前配置要求，跳过行情补数。")

        if decision.action in {"incremental", "backfill"} and not cfg.get("data_quality", {}).get(
            "auto_clean_after_update",
            True,
        ):
            clean_summary = _rebuild_clean_outputs(project=project, config_path=config_path, log=log)

        log("行情准备完成，正在执行覆盖审计。")
        audit_exit_code = script_runner("scripts/audit_db.py", ("--data-mode", "clean"))
        if audit_exit_code != 0:
            raise RuntimeError("数据清洗或覆盖审计失败，请检查日志。")

        clean_window_summary = _validate_clean_coverage(project=project, config_path=config_path)
        audit_summary = _read_audit_summary(paths.meta_dir / "db_coverage_summary.json")
        coverage_ratio = audit_summary.get("clean_coverage_ratio")
        if coverage_ratio is not None:
            log(f"清洗覆盖审计完成，clean 覆盖率 {coverage_ratio:.2%}。")
        else:
            log("清洗覆盖审计完成。")

        summary_payload.update(
            {
                "status": "succeeded",
                "update_request": update_payload,
                "clean_summary": clean_summary,
                "audit_summary": audit_summary,
                "clean_window_summary": clean_window_summary,
            }
        )
        status_path = _write_preparation_status(project, summary_payload)
        update_run_manifest(
            project,
            {
                "prepare_data": {
                    "status": "succeeded",
                    "decision": decision.decision_key,
                    "status_path": str(status_path),
                    "audit_summary_path": str(paths.meta_dir / "db_coverage_summary.json"),
                }
            },
        )
        return decision
    except Exception as exc:
        summary_payload.update(
            {
                "status": "failed",
                "update_request": update_payload,
                "clean_summary": clean_summary,
                "audit_summary": audit_summary,
                "error_message": str(exc),
            }
        )
        status_path = _write_preparation_status(project, summary_payload)
        update_run_manifest(
            project,
            {
                "prepare_data": {
                    "status": "failed",
                    "decision": decision.decision_key,
                    "status_path": str(status_path),
                    "error_message": str(exc),
                }
            },
        )
        raise
