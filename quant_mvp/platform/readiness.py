from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from quant_mvp.config import load_config
from quant_mvp.db import (
    CLEAN_BARS_TABLE,
    RAW_BARS_TABLE,
    coverage_report,
    db_date_range,
    get_conn,
    list_db_codes,
    table_exists,
    table_row_count,
)
from quant_mvp.networking import NetworkRuntimeConfig, classify_network_exception, make_issue, request_with_retry
from quant_mvp.project import resolve_project_paths

from .preparation import determine_preparation_decision
from .schemas import PipelineName
from .settings import PlatformSettings


@dataclass(frozen=True)
class UpstreamSpec:
    key: str
    label: str
    url: str
    method: str
    headers: dict[str, str]
    params: dict[str, str] | None = None
    data: dict[str, str] | None = None


UPSTREAMS: dict[str, UpstreamSpec] = {
    "sse": UpstreamSpec(
        key="sse",
        label="上交所股票列表",
        url="https://query.sse.com.cn/sseQuery/commonQuery.do",
        method="GET",
        headers={
            "Host": "query.sse.com.cn",
            "Pragma": "no-cache",
            "Referer": "https://www.sse.com.cn/assortment/stock/list/share/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        },
        params={
            "STOCK_TYPE": "1",
            "REG_PROVINCE": "",
            "CSRC_CODE": "",
            "STOCK_CODE": "",
            "sqlId": "COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L",
            "COMPANY_STATUS": "2,4,5,7,8",
            "type": "inParams",
            "isPagination": "true",
            "pageHelp.cacheSize": "1",
            "pageHelp.beginPage": "1",
            "pageHelp.pageSize": "5",
            "pageHelp.pageNo": "1",
            "pageHelp.endPage": "1",
        },
    ),
    "szse": UpstreamSpec(
        key="szse",
        label="深交所股票列表",
        url="https://www.szse.cn/api/report/ShowReport",
        method="GET",
        headers={
            "Referer": "https://www.szse.cn/market/product/stock/list/index.html",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        },
        params={
            "SHOWTYPE": "xlsx",
            "CATALOGID": "1110",
            "TABKEY": "tab1",
            "random": "0.123456789",
        },
    ),
    "bse": UpstreamSpec(
        key="bse",
        label="北交所股票列表",
        url="https://www.bse.cn/nqxxController/nqxxCnzq.do",
        method="POST",
        headers={
            "Referer": "https://www.bse.cn/nq/listedcompany.html",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        },
        data={
            "page": "0",
            "typejb": "T",
            "xxfcbj[]": "2",
            "xxzqdm": "",
            "sortfield": "xxzqdm",
            "sorttype": "asc",
        },
    ),
    "eastmoney": UpstreamSpec(
        key="eastmoney",
        label="东方财富历史行情",
        url="https://push2his.eastmoney.com/api/qt/stock/kline/get",
        method="GET",
        headers={
            "Referer": "https://quote.eastmoney.com/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        },
        params={
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "klt": "101",
            "fqt": "1",
            "secid": "0.000001",
            "beg": "20240101",
            "end": "20240131",
        },
    ),
}

DOCTOR_FILENAME = "platform_doctor.json"
READINESS_FILENAME = "platform_readiness.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_raw_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _persist_diagnostics(meta_dir: Path, filename: str, payload: dict[str, Any]) -> None:
    stored = dict(payload)
    stored["generated_at"] = _utc_now_iso()
    _write_json(meta_dir / filename, stored)


def _serialize_date_range(date_range: tuple[str | None, str | None]) -> dict[str, str | None]:
    return {"min": date_range[0], "max": date_range[1]}


def _issue_messages(items: list[dict[str, Any]]) -> list[str]:
    return [item["message"] for item in items]


def _probe_upstream(spec: UpstreamSpec, network_cfg: NetworkRuntimeConfig) -> dict[str, Any]:
    try:
        response, latency_ms = request_with_retry(
            network_cfg,
            method=spec.method,
            url=spec.url,
            headers=spec.headers,
            params=spec.params,
            data=spec.data,
        )
        response.raise_for_status()
        return {
            "key": spec.key,
            "label": spec.label,
            "url": spec.url,
            "reachable": True,
            "http_status": response.status_code,
            "latency_ms": latency_ms,
            "error_code": None,
            "error_summary": None,
            "suggestion": None,
        }
    except Exception as exc:
        issue = classify_network_exception(exc, network_cfg, upstream_label=spec.label)
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        latency_ms = getattr(exc, "_bt_latency_ms", None)
        return {
            "key": spec.key,
            "label": spec.label,
            "url": spec.url,
            "reachable": False,
            "http_status": status_code,
            "latency_ms": latency_ms,
            "error_code": issue["code"],
            "error_summary": issue["message"],
            "suggestion": issue["suggestion"],
        }


def run_network_diagnostics(
    settings: PlatformSettings,
    *,
    upstream_keys: Iterable[str] | None = None,
) -> dict[str, Any]:
    network_cfg = settings.network_config()
    blocking_issue_details = network_cfg.validation_issue_details()
    selected_keys = list(upstream_keys) if upstream_keys is not None else list(UPSTREAMS.keys())
    checks = [_probe_upstream(UPSTREAMS[key], network_cfg) for key in selected_keys]
    return {
        "proxy_url": network_cfg.proxy_url,
        "ca_bundle_path": network_cfg.ca_bundle_path,
        "connect_timeout_seconds": network_cfg.connect_timeout_seconds,
        "read_timeout_seconds": network_cfg.read_timeout_seconds,
        "using_proxy": bool(network_cfg.proxy_url),
        "using_custom_ca": bool(network_cfg.ca_bundle_path),
        "ca_bundle_exists": network_cfg.ca_bundle_exists(),
        "blocking_issues": _issue_messages(blocking_issue_details),
        "blocking_issue_details": blocking_issue_details,
        "warnings": [],
        "checks": checks,
    }


def _load_universe_codes(universe_path: Path) -> list[str]:
    if not universe_path.exists():
        return []
    with open(universe_path, "r", encoding="utf-8") as handle:
        return sorted({line.strip() for line in handle if line.strip()})


def _compute_window_coverage(
    *,
    db_path: Path,
    freq: str,
    start_date: str | None,
    end_date: str | None,
    universe_codes: list[str],
) -> dict[str, Any]:
    if not end_date:
        return {
            "enabled": False,
            "reason": "end_date_missing",
        }
    if not universe_codes:
        return {
            "enabled": False,
            "reason": "universe_missing",
        }

    raw_window = coverage_report(
        db_path=db_path,
        freq=freq,
        codes=universe_codes,
        data_mode="raw",
        start=start_date,
        end=end_date,
    )
    clean_window = coverage_report(
        db_path=db_path,
        freq=freq,
        codes=universe_codes,
        data_mode="clean",
        start=start_date,
        end=end_date,
    )

    expected = len(universe_codes)
    raw_codes_with_data = int((raw_window["bars_count"] > 0).sum()) if not raw_window.empty else 0
    clean_codes_with_data = int((clean_window["bars_count"] > 0).sum()) if not clean_window.empty else 0
    return {
        "enabled": True,
        "window_start": start_date,
        "window_end": end_date,
        "expected_code_count": expected,
        "raw_codes_with_data": raw_codes_with_data,
        "clean_codes_with_data": clean_codes_with_data,
        "raw_missing_code_count": max(0, expected - raw_codes_with_data),
        "clean_missing_code_count": max(0, expected - clean_codes_with_data),
        "raw_rows_in_window": int(raw_window["bars_count"].sum()) if not raw_window.empty else 0,
        "clean_rows_in_window": int(clean_window["bars_count"].sum()) if not clean_window.empty else 0,
        "raw_window_range": _serialize_date_range(
            (
                None if raw_window.empty else raw_window["first_date"].dropna().min(),
                None if raw_window.empty else raw_window["last_date"].dropna().max(),
            )
        ),
        "clean_window_range": _serialize_date_range(
            (
                None if clean_window.empty else clean_window["first_date"].dropna().min(),
                None if clean_window.empty else clean_window["last_date"].dropna().max(),
            )
        ),
    }


def _inspect_database(
    *,
    raw_config: dict[str, Any],
    effective_config: dict[str, Any] | None,
    universe_codes: list[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw_db_path = raw_config.get("db_path")
    source_table = str(raw_config.get("data_quality", {}).get("source_table", RAW_BARS_TABLE))
    clean_table = str(raw_config.get("data_quality", {}).get("clean_table", CLEAN_BARS_TABLE))
    freq = str((effective_config or raw_config).get("freq") or "1d")

    payload: dict[str, Any] = {
        "configured_path": raw_db_path,
        "explicit_configured": raw_db_path not in {None, ""},
        "path_is_absolute": False,
        "exists": False,
        "sqlite_openable": False,
        "tables": [],
        "raw_table": source_table,
        "clean_table": clean_table,
        "raw_rows": 0,
        "clean_rows": 0,
        "raw_codes": 0,
        "clean_codes": 0,
        "raw_date_range": _serialize_date_range((None, None)),
        "clean_date_range": _serialize_date_range((None, None)),
        "file_size_bytes": None,
        "modified_at": None,
        "window_coverage": {"enabled": False, "reason": "db_unavailable"},
        "ready": False,
        "issues": [],
    }
    issues: list[dict[str, Any]] = []

    if raw_db_path in {None, ""}:
        issues.append(
            make_issue(
                "db_path_missing",
                "项目配置缺少显式 db_path，平台不会再回退到仓库内 data/market.db。",
                suggestion="请在项目配置中填写外部 market.db 的绝对路径。",
            )
        )
        payload["issues"] = _issue_messages(issues)
        return payload, issues

    db_path = Path(str(raw_db_path))
    payload["path_is_absolute"] = db_path.is_absolute()
    if not payload["path_is_absolute"]:
        issues.append(
            make_issue(
                "db_path_not_absolute",
                f"db_path 必须是绝对路径：{raw_db_path}",
                suggestion="请把 db_path 改成 Windows 绝对路径，例如 C:/data/market.db。",
            )
        )
        payload["issues"] = _issue_messages(issues)
        return payload, issues

    resolved = db_path.expanduser().resolve()
    payload["resolved_path"] = str(resolved)
    payload["exists"] = resolved.exists()
    if not resolved.exists():
        issues.append(
            make_issue(
                "db_not_found",
                f"外部行情库不存在：{resolved}",
                suggestion="请确认 db_path 是否正确，且当前机器可访问该文件。",
            )
        )
        payload["issues"] = _issue_messages(issues)
        return payload, issues

    stat = resolved.stat()
    payload["file_size_bytes"] = stat.st_size
    payload["modified_at"] = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

    try:
        with get_conn(resolved) as conn:
            payload["sqlite_openable"] = True
            payload["tables"] = sorted(
                row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            )
            raw_exists = table_exists(conn, source_table)
            clean_exists = table_exists(conn, clean_table)
    except sqlite3.DatabaseError:
        issues.append(
            make_issue(
                "db_invalid_sqlite",
                f"外部行情库不是可读的 SQLite 文件：{resolved}",
                suggestion="请确认 db_path 指向的是有效的 SQLite 市场数据文件。",
            )
        )
        payload["issues"] = _issue_messages(issues)
        return payload, issues

    if not raw_exists and not clean_exists:
        issues.append(
            make_issue(
                "db_schema_missing",
                f"外部行情库缺少可识别的行情表，至少需要 {source_table} 或 {clean_table}。",
                suggestion="请确认导入的是平台支持的 market.db，或先执行数据初始化。",
            )
        )
        payload["issues"] = _issue_messages(issues)
        return payload, issues

    payload["raw_rows"] = table_row_count(resolved, source_table, freq=freq) if raw_exists else 0
    payload["clean_rows"] = table_row_count(resolved, clean_table, freq=freq) if clean_exists else 0
    payload["raw_codes"] = len(list_db_codes(resolved, freq=freq, data_mode="raw")) if raw_exists else 0
    payload["clean_codes"] = len(list_db_codes(resolved, freq=freq, data_mode="clean")) if clean_exists else 0
    if raw_exists:
        payload["raw_date_range"] = _serialize_date_range(db_date_range(resolved, freq=freq, data_mode="raw"))
    if clean_exists:
        payload["clean_date_range"] = _serialize_date_range(db_date_range(resolved, freq=freq, data_mode="clean"))

    if payload["raw_rows"] <= 0 and payload["clean_rows"] <= 0:
        issues.append(
            make_issue(
                "db_schema_missing",
                f"外部行情库已找到，但 {source_table}/{clean_table} 都没有可用数据。",
                suggestion="请确认数据库是否已导入行情，或重新执行数据初始化。",
            )
        )
        payload["issues"] = _issue_messages(issues)
        return payload, issues

    if effective_config is not None:
        payload["window_coverage"] = _compute_window_coverage(
            db_path=resolved,
            freq=freq,
            start_date=str(effective_config.get("start_date")) if effective_config.get("start_date") else None,
            end_date=str(effective_config.get("end_date")) if effective_config.get("end_date") else None,
            universe_codes=universe_codes,
        )

    payload["ready"] = True
    payload["issues"] = _issue_messages(issues)
    return payload, issues


def _required_upstreams(
    *,
    pipeline: str | None,
    decision_key: str | None,
    universe_missing: bool,
    db_status: dict[str, Any],
) -> list[str]:
    required: list[str] = []
    if universe_missing and db_status.get("raw_codes", 0) <= 0 and db_status.get("clean_codes", 0) <= 0:
        required.extend(["sse", "szse"])
    if decision_key in {"incremental", "backfill"}:
        required.append("eastmoney")
    if pipeline == PipelineName.data_refresh.value and "eastmoney" not in required:
        required.append("eastmoney")
    return required


def _decision_payload(decision) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if decision is None:
        return (
            {
                "action": None,
                "decision_key": None,
                "reason": None,
                "rebuild_clean_only": False,
            },
            [],
        )
    return (
        {
            "action": decision.action,
            "decision_key": decision.decision_key,
            "reason": decision.reason,
            "rebuild_clean_only": decision.rebuild_clean_only,
        },
        decision.trace,
    )


def _config_status(config_path: Path) -> dict[str, Any]:
    return {
        "path": str(config_path),
        "exists": config_path.exists(),
    }


def _diagnose_project(
    *,
    settings: PlatformSettings,
    project: str,
    pipeline: str | None,
    config_path_override: Path | None,
    check_all_upstreams: bool,
    persist_filename: str | None,
) -> dict[str, Any]:
    repo_root = settings.normalized_repo_root()
    paths = resolve_project_paths(project, root=repo_root)
    config_path = config_path_override.resolve() if config_path_override else paths.config_path
    raw_config = _read_raw_config(config_path)
    universe_codes = _load_universe_codes(paths.universe_path)
    universe_exists = bool(universe_codes)

    effective_config: dict[str, Any] | None = None
    warning_details: list[dict[str, Any]] = []
    if config_path.exists() and raw_config.get("db_path") not in {None, ""}:
        try:
            effective_config, _ = load_config(project, config_path=config_path)
        except Exception as exc:
            warning_details.append(
                make_issue(
                    "config_load_failed",
                    f"无法加载项目配置：{exc}",
                    suggestion="请检查 JSON 配置格式和字段类型。",
                )
            )

    db_status, db_issue_details = _inspect_database(
        raw_config=raw_config,
        effective_config=effective_config,
        universe_codes=universe_codes,
    )
    blocking_issue_details = list(db_issue_details)

    decision = None
    if config_path.exists() and db_status["ready"]:
        try:
            decision = determine_preparation_decision(
                project=project,
                config_path=config_path,
                repo_root=repo_root,
            )
        except Exception as exc:
            warning_details.append(
                make_issue(
                    "prepare_decision_failed",
                    f"无法预演数据准备决策：{exc}",
                    suggestion="请检查项目配置、股票池和数据库结构。",
                )
            )

    preparation, decision_trace = _decision_payload(decision)
    required_upstreams = _required_upstreams(
        pipeline=pipeline,
        decision_key=preparation["decision_key"],
        universe_missing=not universe_exists,
        db_status=db_status,
    )
    network_status = run_network_diagnostics(
        settings,
        upstream_keys=None if check_all_upstreams else required_upstreams,
    )
    blocking_issue_details.extend(network_status["blocking_issue_details"])

    checks_by_key = {item["key"]: item for item in network_status["checks"]}
    for key in required_upstreams:
        check = checks_by_key.get(key)
        if check and check["reachable"]:
            continue
        blocking_issue_details.append(
            make_issue(
                check["error_code"] if check else "upstream_http_error",
                (check["error_summary"] if check else f"无法连接上游数据源：{key}") or f"无法连接上游数据源：{key}",
                suggestion=(check["suggestion"] if check else "请检查网络、代理和 CA 证书配置。"),
                detail={"upstream": key},
            )
        )

    if not config_path.exists():
        blocking_issue_details.append(
            make_issue(
                "config_not_found",
                f"项目配置不存在：{config_path}",
                suggestion="请先创建项目配置文件，或在 doctor CLI 中显式传入 --config。",
            )
        )

    result = {
        "project": project,
        "pipeline": pipeline,
        "ready": not blocking_issue_details,
        "config": _config_status(config_path),
        "config_path": str(config_path),
        "universe_exists": universe_exists,
        "universe_path": str(paths.universe_path),
        "db_status": db_status,
        "network_status": network_status,
        "preparation": preparation,
        "decision_trace": decision_trace,
        "required_upstreams": required_upstreams,
        "blocking_issue_details": blocking_issue_details,
        "warning_details": warning_details,
        "blocking_issues": _issue_messages(blocking_issue_details),
        "warnings": _issue_messages(warning_details),
    }

    if persist_filename:
        _persist_diagnostics(paths.meta_dir, persist_filename, result)
    return result


def project_readiness(
    *,
    settings: PlatformSettings,
    project: str,
    pipeline: str | None = None,
    config_path_override: Path | None = None,
) -> dict[str, Any]:
    return _diagnose_project(
        settings=settings,
        project=project,
        pipeline=pipeline,
        config_path_override=config_path_override,
        check_all_upstreams=False,
        persist_filename=READINESS_FILENAME,
    )


def project_doctor(
    *,
    settings: PlatformSettings,
    project: str,
    pipeline: str | None = None,
    config_path_override: Path | None = None,
) -> dict[str, Any]:
    return _diagnose_project(
        settings=settings,
        project=project,
        pipeline=pipeline,
        config_path_override=config_path_override,
        check_all_upstreams=True,
        persist_filename=DOCTOR_FILENAME,
    )
