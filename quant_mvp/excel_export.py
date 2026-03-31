from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .memory.writeback import bootstrap_memory_files, load_machine_state
from .project import ProjectPaths, find_repo_root


FEED_VERSION = "excel_console_feed_v2"
WORKBOOK_NAME = "ResearchConsole.xlsm"
WORKSHEET_NAMES = ("Control", "Overview", "Strategies", "Experiments", "Runs", "Artifacts")
_HEADER_FILL = PatternFill(fill_type="solid", fgColor="1F4E78")
_HEADER_FONT = Font(color="FFFFFF", bold=True)
_TITLE_FONT = Font(size=18, bold=True)
_BUTTON_FILL = PatternFill(fill_type="solid", fgColor="D9EAF7")
_BUTTON_FONT = Font(color="0B5394", bold=True, underline="single")
_CAUTION_FILL = PatternFill(fill_type="solid", fgColor="FCE5CD")
_SUCCESS_FILL = PatternFill(fill_type="solid", fgColor="D9EAD3")
_DANGER_FILL = PatternFill(fill_type="solid", fgColor="F4CCCC")
_NEUTRAL_FILL = PatternFill(fill_type="solid", fgColor="EDEDED")
_CARD_FILL = PatternFill(fill_type="solid", fgColor="F7F9FC")
_SUBTLE_FILL = PatternFill(fill_type="solid", fgColor="F3F6FA")
_THIN_SIDE = Side(style="thin", color="D9D9D9")
_BOX_BORDER = Border(left=_THIN_SIDE, right=_THIN_SIDE, top=_THIN_SIDE, bottom=_THIN_SIDE)
_SECTION_TITLE_FONT = Font(size=12, bold=True, color="FFFFFF")
_LABEL_FONT = Font(bold=True, color="2F2F2F")
_SMALL_MUTED_FONT = Font(size=10, color="666666")
_METRIC_VALUE_FONT = Font(size=16, bold=True, color="1F1F1F")

_STRATEGY_LABELS = {
    "f1_elasticnet_v1": "F1 ElasticNet",
    "f2_structured_latent_factor_v1": "F2.1 Structured Latent",
    "baseline_limit_up": "Baseline Control",
    "r1_predictive_error_overlay_v1": "R1.1 Overlay",
    "r1_predictive_error_overlay_v2": "R1.2 Overlay",
    "risk_constrained_limit_up": "Risk-Constrained Limit Up",
    "tighter_entry_limit_up": "Tighter Entry Limit Up",
    "hybrid_f1_5_frozen_sidecar": "Hybrid F1.5 Frozen Sidecar",
    "legacy_single_branch": "Legacy Single Branch",
}


@dataclass(frozen=True)
class ExcelConsolePaths:
    root: Path
    feed_dir: Path
    actions_dir: Path
    workbook_path: Path
    manifest_path: Path
    notes_path: Path
    vba_dir: Path
    vba_module_path: Path
    open_latest_console_cmd: Path


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return dict(default or {})


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _first(iterable: Iterable[str]) -> str:
    for item in iterable:
        text = _normalize_text(item)
        if text:
            return text
    return ""


def _display_strategy_name(strategy_id: str, raw_name: Any) -> str:
    strategy_text = _normalize_text(strategy_id)
    name_text = _normalize_text(raw_name)
    if strategy_text in _STRATEGY_LABELS:
        return _STRATEGY_LABELS[strategy_text]
    if "?" in name_text or "\ufffd" in name_text:
        return strategy_text or name_text
    return name_text or strategy_text


def _read_report(path_text: str) -> dict[str, Any]:
    if not path_text:
        return {}
    try:
        return _read_json(Path(path_text), default={})
    except OSError:
        return {}


def _coerce_float(value: Any) -> float | None:
    try:
        if value in ("", None):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_pct(value: Any) -> str:
    number = _coerce_float(value)
    if number is None:
        return ""
    return f"{number * 100:.2f}%"


def _fmt_float(value: Any, digits: int = 2) -> str:
    number = _coerce_float(value)
    if number is None:
        return ""
    return f"{number:.{digits}f}"


def _card_fill_for_status(status: str) -> PatternFill:
    text = _normalize_text(status).lower()
    if any(token in text for token in ("pass", "promote", "ready", "mainline", "accepted")):
        return _SUCCESS_FILL
    if any(token in text for token in ("reject", "blocked", "above", "fail")):
        return _DANGER_FILL
    if any(token in text for token in ("mixed", "hold", "continue", "challenger")):
        return _CAUTION_FILL
    return _CARD_FILL


def _excel_console_paths(paths: ProjectPaths) -> ExcelConsolePaths:
    root = paths.artifacts_dir / "excel"
    feed_dir = root / "feed"
    actions_dir = root / "actions"
    vba_dir = root / "vba"
    return ExcelConsolePaths(
        root=root,
        feed_dir=feed_dir,
        actions_dir=actions_dir,
        workbook_path=root / WORKBOOK_NAME,
        manifest_path=feed_dir / "manifest.json",
        notes_path=root / "EXCEL_CONSOLE_NOTES.md",
        vba_dir=vba_dir,
        vba_module_path=vba_dir / "ResearchConsoleModule.bas",
        open_latest_console_cmd=actions_dir / "open_latest_console.cmd",
    )


def _ensure_excel_dirs(console_paths: ExcelConsolePaths) -> None:
    console_paths.root.mkdir(parents=True, exist_ok=True)
    console_paths.feed_dir.mkdir(parents=True, exist_ok=True)
    console_paths.actions_dir.mkdir(parents=True, exist_ok=True)
    console_paths.vba_dir.mkdir(parents=True, exist_ok=True)


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
    return path


def _quote_cmd(value: Path | str) -> str:
    return f'"{str(value)}"'


def _quote_powershell_single(value: Path | str) -> str:
    return str(value).replace("'", "''")


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return path


def _probe_excel_vba_status() -> dict[str, Any]:
    probe_script = (
        "$excel = $null; $wb = $null;"
        "try {"
        "$excel = New-Object -ComObject Excel.Application;"
        "$excel.Visible = $false;"
        "$excel.DisplayAlerts = $false;"
        "$wb = $excel.Workbooks.Add();"
        "$proj = $wb.VBProject;"
        "if ($null -eq $proj) {"
        "$result = @{ excel_com_available = $true; vbproject_access = $false; status = 'blocked_vbproject_access'; detail = 'VBProject is null; Trust access to the VBA project object model is likely disabled.' }"
        "} else {"
        "$result = @{ excel_com_available = $true; vbproject_access = $true; status = 'vbproject_access_available'; detail = 'VBProject access is available.' }"
        "}"
        "} catch {"
        "$result = @{ excel_com_available = $false; vbproject_access = $false; status = 'excel_com_unavailable'; detail = $_.Exception.Message }"
        "} finally {"
        "if ($wb -ne $null) { $wb.Close($false) | Out-Null }"
        "if ($excel -ne $null) { $excel.Quit() | Out-Null }"
        "}"
        "$result | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", probe_script],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError as exc:
        return {
            "excel_com_available": False,
            "vbproject_access": False,
            "status": "excel_probe_unavailable",
            "detail": str(exc),
        }
    raw = (completed.stdout or "").strip()
    if not raw:
        return {
            "excel_com_available": False,
            "vbproject_access": False,
            "status": "excel_probe_unavailable",
            "detail": (completed.stderr or "No probe output returned.").strip(),
        }
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "excel_com_available": False,
            "vbproject_access": False,
            "status": "excel_probe_parse_failed",
            "detail": raw,
        }
    if not isinstance(payload, dict):
        return {
            "excel_com_available": False,
            "vbproject_access": False,
            "status": "excel_probe_invalid_payload",
            "detail": raw,
        }
    return payload


def _convert_xlsx_to_xlsm(source_xlsx: Path, target_xlsm: Path) -> None:
    target_xlsm.unlink(missing_ok=True)
    source_text = _quote_powershell_single(source_xlsx)
    target_text = _quote_powershell_single(target_xlsm)
    convert_script = (
        "$excel = $null; $wb = $null;"
        "try {"
        "$excel = New-Object -ComObject Excel.Application;"
        "$excel.Visible = $false;"
        "$excel.DisplayAlerts = $false;"
        f"$source = '{source_text}';"
        f"$target = '{target_text}';"
        "$wb = $excel.Workbooks.Open($source);"
        "$wb.SaveAs($target, 52);"
        "} finally {"
        "if ($wb -ne $null) { $wb.Close($false) | Out-Null }"
        "if ($excel -ne $null) { $excel.Quit() | Out-Null }"
        "}"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", convert_script],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode == 0 and target_xlsm.exists() and _is_valid_xlsm(target_xlsm):
        return
    stderr = (completed.stderr or completed.stdout or "").strip()
    lowered = stderr.lower()
    if "cannot access" in lowered or "无法访问" in stderr or "另存为" in stderr:
        raise PermissionError(stderr or f"Failed to write workbook: {target_xlsm}")
    if target_xlsm.exists() and not _is_valid_xlsm(target_xlsm):
        raise RuntimeError(f"Excel SaveAs returned an invalid .xlsm package: {target_xlsm}")
    raise RuntimeError(stderr or f"Failed to convert {source_xlsx} to {target_xlsm}")


def _is_valid_xlsm(path: Path) -> bool:
    if not path.exists() or not zipfile.is_zipfile(path):
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            content_types = archive.read("[Content_Types].xml").decode("utf-8", errors="ignore")
    except (KeyError, OSError, zipfile.BadZipFile):
        return False
    return "application/vnd.ms-excel.sheet.macroEnabled.main+xml" in content_types


def _overview_rows(state: dict[str, Any], *, workbook_mode: str, workbook_path: Path) -> list[dict[str, Any]]:
    primary = ", ".join(state.get("current_primary_strategy_ids", []) or [])
    secondary = ", ".join(state.get("current_secondary_strategy_ids", []) or [])
    blocked = ", ".join(state.get("current_blocked_strategy_ids", []) or [])
    readiness = dict(state.get("readiness", {}) or {})
    return [
        {"section": "Project", "key": "project", "value": state.get("project", ""), "display_order": 10},
        {"section": "Project", "key": "phase", "value": state.get("current_phase", ""), "display_order": 20},
        {"section": "Project", "key": "current_task", "value": state.get("current_task", ""), "display_order": 30},
        {"section": "Project", "key": "current_blocker", "value": state.get("current_blocker", ""), "display_order": 40},
        {"section": "Project", "key": "next_priority_action", "value": state.get("next_priority_action", ""), "display_order": 50},
        {"section": "Research", "key": "primary_strategy_ids", "value": primary, "display_order": 60},
        {"section": "Research", "key": "secondary_strategy_ids", "value": secondary, "display_order": 70},
        {"section": "Research", "key": "blocked_strategy_ids", "value": blocked, "display_order": 80},
        {"section": "Research", "key": "last_verified_capability", "value": state.get("last_verified_capability", ""), "display_order": 90},
        {"section": "Research", "key": "readiness_stage", "value": readiness.get("stage", ""), "display_order": 100},
        {"section": "Platform", "key": "canonical_universe_id", "value": state.get("canonical_universe_id", ""), "display_order": 110},
        {"section": "Platform", "key": "effective_subagent_gate_mode", "value": state.get("effective_subagent_gate_mode", ""), "display_order": 120},
        {"section": "Platform", "key": "excel_console_mode", "value": workbook_mode, "display_order": 130},
        {"section": "Platform", "key": "excel_console_path", "value": str(workbook_path), "display_order": 140},
    ]


def _strategy_metrics_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = {
        _normalize_text(item.get("strategy_id")): item
        for item in (state.get("strategy_candidates", []) or [])
        if isinstance(item, dict) and _normalize_text(item.get("strategy_id"))
    }
    rows: list[dict[str, Any]] = []

    def add_row(
        *,
        strategy_id: str,
        metrics: dict[str, Any],
        decision: str = "",
        classification: str = "",
        artifact_ref: str = "",
        track: str = "",
    ) -> None:
        candidate = candidates.get(strategy_id, {})
        rows.append(
            {
                "strategy_id": strategy_id,
                "name": _display_strategy_name(strategy_id, candidate.get("name")),
                "track": track or _normalize_text(candidate.get("track")),
                "decision": decision or _normalize_text(candidate.get("decision")),
                "classification": classification,
                "annualized_return": _coerce_float(metrics.get("annualized_return")),
                "max_drawdown": _coerce_float(metrics.get("max_drawdown")),
                "sharpe_ratio": _coerce_float(metrics.get("sharpe_ratio")),
                "calmar_ratio": _coerce_float(metrics.get("calmar_ratio")),
                "turnover": _coerce_float(metrics.get("turnover")),
                "win_rate": _coerce_float(metrics.get("win_rate")),
                "artifact_ref": artifact_ref,
            }
        )

    f1_report = _read_report(_normalize_text(state.get("f1_verifier_report_path")))
    if f1_report:
        add_row(
            strategy_id="baseline_limit_up",
            metrics=dict(f1_report.get("control_metrics") or {}),
            decision="control",
            classification=_normalize_text(f1_report.get("classification")),
            artifact_ref=_normalize_text(f1_report.get("artifact_paths", {}).get("plot_path")),
            track="control",
        )
        add_row(
            strategy_id="f1_elasticnet_v1",
            metrics=dict(f1_report.get("f1_metrics") or {}),
            decision=_normalize_text(f1_report.get("decision")),
            classification=_normalize_text(f1_report.get("classification")),
            artifact_ref=_normalize_text(f1_report.get("artifact_paths", {}).get("plot_path")),
            track="primary",
        )

    r1_report = _read_report(_normalize_text(state.get("r1_verify_report_path")))
    if r1_report:
        regime_profile = _normalize_text(r1_report.get("regime_control", {}).get("profile"))
        strategy_id = "r1_predictive_error_overlay_v2" if regime_profile.endswith("_v2") else "r1_predictive_error_overlay_v1"
        add_row(
            strategy_id=strategy_id,
            metrics=dict(r1_report.get("r1_metrics") or {}),
            decision=_normalize_text(r1_report.get("decision")),
            classification=_normalize_text(r1_report.get("classification")),
            artifact_ref=_normalize_text(r1_report.get("artifact_paths", {}).get("plot_path")),
            track="candidate",
        )

    f2_report = _read_report(_normalize_text(state.get("f2_verify_report_path")))
    if f2_report:
        add_row(
            strategy_id="f2_structured_latent_factor_v1",
            metrics=dict(f2_report.get("f2_metrics") or {}),
            decision=_normalize_text(f2_report.get("decision")),
            classification=_normalize_text(f2_report.get("classification")),
            artifact_ref=_normalize_text(f2_report.get("artifact_paths", {}).get("plot_path")),
            track="candidate",
        )

    seen = {row["strategy_id"] for row in rows}
    for strategy_id, candidate in candidates.items():
        if strategy_id in seen:
            continue
        rows.append(
            {
                "strategy_id": strategy_id,
                "name": _display_strategy_name(strategy_id, candidate.get("name")),
                "track": _normalize_text(candidate.get("track")),
                "decision": _normalize_text(candidate.get("decision")),
                "classification": "",
                "annualized_return": None,
                "max_drawdown": None,
                "sharpe_ratio": None,
                "calmar_ratio": None,
                "turnover": None,
                "win_rate": None,
                "artifact_ref": _first([str(item).strip() for item in candidate.get("artifact_refs", []) if str(item).strip()]),
            }
        )
    return rows


def _preview_plot_rows(state: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for label, key in (
        ("F2 对照图", "f2_verify_report_path"),
        ("F1 对照图", "f1_verifier_report_path"),
        ("R1 对照图", "r1_verify_report_path"),
    ):
        report = _read_report(_normalize_text(state.get(key)))
        plot_path = _normalize_text(report.get("artifact_paths", {}).get("plot_path"))
        if not plot_path or plot_path in seen:
            continue
        seen.add(plot_path)
        rows.append({"label": label, "path": plot_path})
    return rows


def _strategies_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in state.get("strategy_candidates", []) or []:
        if not isinstance(candidate, dict):
            continue
        artifact_refs = [str(item).strip() for item in candidate.get("artifact_refs", []) if str(item).strip()]
        rows.append(
            {
                "strategy_id": _normalize_text(candidate.get("strategy_id")),
                "name": _normalize_text(candidate.get("name")),
                "track": _normalize_text(candidate.get("track")),
                "current_stage": _normalize_text(candidate.get("current_stage")),
                "decision": _normalize_text(candidate.get("decision")),
                "latest_result": _normalize_text(candidate.get("latest_result")),
                "next_validation": _normalize_text(candidate.get("next_validation")),
                "artifact_ref": _first(artifact_refs),
            }
        )
    return rows


def _experiment_summary_rows(paths: ProjectPaths) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for item in _read_jsonl(paths.experiment_ledger_path)[-100:]:
        counter[_normalize_text(item.get("result")) or "unknown"] += 1
    rows: list[dict[str, Any]] = []
    for classification, count in sorted(counter.items(), key=lambda pair: (-pair[1], pair[0])):
        rows.append({"classification": classification, "count": count})
    return rows


def _experiments_rows(paths: ProjectPaths) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in list(reversed(_read_jsonl(paths.experiment_ledger_path)))[:100]:
        artifact_refs = [str(entry).strip() for entry in item.get("artifact_refs", []) if str(entry).strip()]
        rows.append(
            {
                "experiment_id": _normalize_text(item.get("experiment_id")),
                "timestamp": _normalize_text(item.get("timestamp")),
                "mode": _normalize_text(item.get("result")),
                "strategy_candidate_id": _normalize_text(item.get("strategy_candidate_id") or item.get("hypothesis")),
                "classification": _normalize_text(item.get("result")),
                "summary": _normalize_text(item.get("hypothesis")) or _normalize_text(item.get("result")),
                "report_path": _first(artifact_refs),
            }
        )
    rows.reverse()
    return rows


def _runs_rows(paths: ProjectPaths) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in list(reversed(_read_jsonl(paths.experiment_ledger_path)))[:100]:
        artifact_refs = [str(entry).strip() for entry in item.get("artifact_refs", []) if str(entry).strip()]
        blockers = [str(entry).strip() for entry in item.get("blockers", []) if str(entry).strip()]
        summary = _normalize_text(item.get("hypothesis")) or "; ".join(blockers) or _normalize_text(item.get("result"))
        rows.append(
            {
                "run_id": _normalize_text(item.get("experiment_id")),
                "kind": _normalize_text(item.get("result")),
                "status": _normalize_text(item.get("result")),
                "started_at": _normalize_text(item.get("timestamp")),
                "finished_at": _normalize_text(item.get("timestamp")),
                "summary": summary,
                "artifact_path": _first(artifact_refs),
            }
        )
    rows.reverse()
    return rows


def _artifact_type(path: str) -> str:
    lowered = path.lower()
    if lowered.endswith(".png"):
        return "plot_png"
    if lowered.endswith(".md"):
        return "report_markdown"
    if lowered.endswith(".json"):
        return "report_json"
    if lowered.endswith(".csv"):
        return "table_csv"
    if lowered.endswith(".xlsm"):
        return "excel_console"
    if lowered.endswith(".cmd"):
        return "launcher_script"
    return "artifact"


def _artifacts_rows(
    paths: ProjectPaths,
    state: dict[str, Any],
    console_paths: ExcelConsolePaths,
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    refs: list[tuple[str, str]] = []
    for key, value in sorted(state.items()):
        if key.endswith("_report_path") and value:
            refs.append((key, str(value)))
    for candidate in state.get("strategy_candidates", []) or []:
        if not isinstance(candidate, dict):
            continue
        for ref in candidate.get("artifact_refs", []) or []:
            if ref:
                refs.append((str(candidate.get("strategy_id", "strategy_artifact")), str(ref)))
    for ledger_row in _read_jsonl(paths.experiment_ledger_path)[-50:]:
        for ref in ledger_row.get("artifact_refs", []) or []:
            if ref:
                refs.append((str(ledger_row.get("experiment_id", "experiment_artifact")), str(ref)))
    refs.extend(
        [
            ("project_state", str(paths.project_state_path)),
            ("research_memory", str(paths.research_memory_path)),
            ("strategy_board", str(paths.strategy_board_path)),
            ("verify_last", str(paths.verify_last_path)),
            ("handoff", str(paths.handoff_path)),
            ("migration_prompt", str(paths.migration_prompt_path)),
            ("session_state", str(paths.session_state_path)),
            ("excel_manifest", str(console_paths.manifest_path)),
            ("excel_console", str(Path(manifest.get("effective_workbook_path", console_paths.workbook_path)))),
        ]
    )
    rows: list[dict[str, Any]] = []
    for name, ref in refs:
        ref_text = _normalize_text(ref)
        if not ref_text or ref_text in seen:
            continue
        seen.add(ref_text)
        rows.append(
            {
                "artifact_type": _artifact_type(ref_text),
                "name": _normalize_text(name),
                "path": ref_text,
                "notes": "",
            }
        )
    return rows


def _columns_widths(rows: list[dict[str, Any]], columns: list[str]) -> dict[int, float]:
    widths: dict[int, float] = {}
    for index, column in enumerate(columns, start=1):
        max_len = len(column)
        for row in rows:
            max_len = max(max_len, len(str(row.get(column, ""))))
        widths[index] = max(12.0, min(float(max_len + 2), 60.0))
    return widths


def _style_header_row(ws: Worksheet, row_idx: int, columns: list[str]) -> None:
    for index, column in enumerate(columns, start=1):
        cell = ws.cell(row=row_idx, column=index, value=column)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.border = _BOX_BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center")


def _apply_path_hyperlink(cell, path_text: str) -> None:
    if not path_text:
        return
    cell.hyperlink = path_text
    cell.style = "Hyperlink"


def _write_metric_card(
    ws: Worksheet,
    *,
    start_cell: str,
    end_cell: str,
    title: str,
    value: str,
    fill: PatternFill = _CARD_FILL,
) -> None:
    ws.merge_cells(f"{start_cell}:{end_cell}")
    cell = ws[start_cell]
    cell.value = f"{title}\n{value}"
    cell.fill = fill
    cell.border = _BOX_BORDER
    cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="left")
    cell.font = Font(size=12, bold=True)


def _append_strategy_metric_table(
    ws: Worksheet,
    *,
    start_row: int,
    rows: list[dict[str, Any]],
) -> tuple[int, int]:
    columns = [
        "strategy_id",
        "name",
        "track",
        "decision",
        "annualized_return",
        "max_drawdown",
        "sharpe_ratio",
        "calmar_ratio",
        "turnover",
    ]
    labels = {
        "strategy_id": "策略 ID",
        "name": "名称",
        "track": "轨道",
        "decision": "当前结论",
        "annualized_return": "年化",
        "max_drawdown": "最大回撤",
        "sharpe_ratio": "Sharpe",
        "calmar_ratio": "Calmar",
        "turnover": "换手",
    }
    header_row = start_row
    _style_header_row(ws, header_row, columns)
    current_row = header_row + 1
    for row in rows:
        for index, column in enumerate(columns, start=1):
            raw_value = row.get(column)
            cell = ws.cell(row=current_row, column=index)
            if column in {"annualized_return", "max_drawdown", "turnover"}:
                metric_value = _coerce_float(raw_value)
                cell.value = metric_value
                cell.number_format = "0.00%"
            elif column in {"sharpe_ratio", "calmar_ratio"}:
                metric_value = _coerce_float(raw_value)
                cell.value = metric_value
                cell.number_format = "0.000"
            else:
                cell.value = raw_value
            cell.border = _BOX_BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if column == "decision":
                cell.fill = _card_fill_for_status(_normalize_text(raw_value))
            if column == "name" and row.get("artifact_ref"):
                _apply_path_hyperlink(cell, str(row.get("artifact_ref")))
        current_row += 1
    widths = {
        "A": 28,
        "B": 28,
        "C": 12,
        "D": 26,
        "E": 12,
        "F": 12,
        "G": 10,
        "H": 10,
        "I": 10,
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    return header_row, current_row - 1


def _add_strategy_comparison_chart(
    ws: Worksheet,
    *,
    data_start_row: int,
    data_end_row: int,
    anchor: str,
) -> None:
    if data_end_row <= data_start_row:
        return
    chart = BarChart()
    chart.type = "bar"
    chart.style = 10
    chart.height = 7
    chart.width = 12
    chart.title = "Strategy metric comparison"
    chart.y_axis.title = "strategy"
    chart.x_axis.title = "value"
    data = Reference(ws, min_col=5, min_row=data_start_row, max_col=8, max_row=data_end_row)
    categories = Reference(ws, min_col=2, min_row=data_start_row + 1, max_row=data_end_row)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(categories)
    chart.overlap = 0
    ws.add_chart(chart, anchor)


def _add_experiment_summary_chart(
    ws: Worksheet,
    *,
    start_row: int,
    rows: list[dict[str, Any]],
    anchor: str,
) -> None:
    if not rows:
        return
    ws.cell(row=start_row, column=1, value="result").font = _HEADER_FONT
    ws.cell(row=start_row, column=1).fill = _HEADER_FILL
    ws.cell(row=start_row, column=2, value="count").font = _HEADER_FONT
    ws.cell(row=start_row, column=2).fill = _HEADER_FILL
    current_row = start_row + 1
    for row in rows:
        ws.cell(row=current_row, column=1, value=row["classification"]).border = _BOX_BORDER
        ws.cell(row=current_row, column=2, value=row["count"]).border = _BOX_BORDER
        current_row += 1
    chart = BarChart()
    chart.type = "col"
    chart.style = 11
    chart.height = 6
    chart.width = 9
    chart.title = "Recent experiment results"
    data = Reference(ws, min_col=2, min_row=start_row, max_row=current_row - 1)
    categories = Reference(ws, min_col=1, min_row=start_row + 1, max_row=current_row - 1)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(categories)
    ws.add_chart(chart, anchor)


def _add_preview_image(ws: Worksheet, *, image_path: str, anchor: str, target_width: int = 520) -> None:
    path = Path(image_path)
    if not path.exists():
        return
    image = XLImage(str(path))
    if image.width and image.height:
        ratio = target_width / float(image.width)
        image.width = target_width
        image.height = int(image.height * ratio)
    ws.add_image(image, anchor)


def _write_table_sheet(
    ws: Worksheet,
    *,
    title: str,
    rows: list[dict[str, Any]],
    columns: list[str],
    title_row: int = 1,
    start_row: int = 3,
) -> None:
    title_cell = ws.cell(row=title_row, column=1, value=title)
    title_cell.font = _TITLE_FONT
    title_cell.alignment = Alignment(horizontal="left")
    _style_header_row(ws, start_row, columns)
    current_row = start_row + 1
    path_like_columns = {"artifact_ref", "report_path", "artifact_path", "path"}
    for row in rows:
        for index, column in enumerate(columns, start=1):
            value = row.get(column, "")
            cell = ws.cell(row=current_row, column=index, value=value)
            cell.border = _BOX_BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if column in path_like_columns and value:
                _apply_path_hyperlink(cell, str(value))
        current_row += 1
    end_column = get_column_letter(len(columns))
    end_row = max(start_row + 1, current_row - 1)
    ws.freeze_panes = f"A{start_row + 1}"
    ws.auto_filter.ref = f"A{start_row}:{end_column}{end_row}"
    for index, width in _columns_widths(rows, columns).items():
        ws.column_dimensions[get_column_letter(index)].width = width


def _write_overview_sheet(
    ws: Worksheet,
    overview_rows: list[dict[str, Any]],
    *,
    strategy_metrics_rows: list[dict[str, Any]],
    experiment_summary_rows: list[dict[str, Any]],
) -> None:
    ws.sheet_view.showGridLines = False
    ws.merge_cells("A1:H1")
    ws["A1"] = "Project Overview / 项目总览"
    ws["A1"].font = _TITLE_FONT
    ws["A1"].alignment = Alignment(horizontal="left")

    primary = next((row for row in strategy_metrics_rows if row["strategy_id"] == "f1_elasticnet_v1"), {})
    challenger = next((row for row in strategy_metrics_rows if row["strategy_id"] == "f2_structured_latent_factor_v1"), {})
    _write_metric_card(
        ws,
        start_cell="A3",
        end_cell="B5",
        title="当前主线",
        value=_display_strategy_name("f1_elasticnet_v1", primary.get("name")),
        fill=_SUCCESS_FILL,
    )
    _write_metric_card(
        ws,
        start_cell="C3",
        end_cell="D5",
        title="F1 年化",
        value=_fmt_pct(primary.get("annualized_return")) or "n/a",
        fill=_CARD_FILL,
    )
    _write_metric_card(
        ws,
        start_cell="E3",
        end_cell="F5",
        title="F2 annualized",
        value=_fmt_pct(challenger.get("annualized_return")) or "n/a",
        fill=_CARD_FILL,
    )
    _write_metric_card(
        ws,
        start_cell="G3",
        end_cell="H5",
        title="Current blocker",
        value=_first(item["value"] for item in overview_rows if item["key"] == "current_blocker") or "n/a",
        fill=_CAUTION_FILL,
    )

    row = 7
    current_section = None
    for item in sorted(overview_rows, key=lambda entry: (entry["section"], int(entry["display_order"]))):
        section = str(item["section"])
        if section != current_section:
            ws.cell(row=row, column=1, value=section).font = _SECTION_TITLE_FONT
            ws.cell(row=row, column=1).fill = _HEADER_FILL
            ws.cell(row=row, column=1).border = _BOX_BORDER
            ws.cell(row=row, column=2).fill = _HEADER_FILL
            ws.cell(row=row, column=2).border = _BOX_BORDER
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
            current_section = section
            row += 1
        key_cell = ws.cell(row=row, column=1, value=str(item["key"]))
        value_cell = ws.cell(row=row, column=2, value=str(item["value"]))
        key_cell.font = _LABEL_FONT
        key_cell.border = _BOX_BORDER
        value_cell.border = _BOX_BORDER
        value_cell.alignment = Alignment(wrap_text=True, vertical="top")
        row += 1

    _add_experiment_summary_chart(ws, start_row=max(row + 2, 22), rows=experiment_summary_rows, anchor="J3")

    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 54
    ws.freeze_panes = "A7"


def _button_cell(ws: Worksheet, cell_ref: str, *, label: str, target: Path) -> None:
    cell = ws[cell_ref]
    cell.value = label
    cell.fill = _BUTTON_FILL
    cell.font = _BUTTON_FONT
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = _BOX_BORDER
    cell.hyperlink = str(target)


def _write_control_sheet(
    ws: Worksheet,
    *,
    project: str,
    state: dict[str, Any],
    manifest: dict[str, Any],
    action_scripts: dict[str, Path],
    console_paths: ExcelConsolePaths,
    strategy_metrics_rows: list[dict[str, Any]],
    experiment_summary_rows: list[dict[str, Any]],
    preview_plot_rows: list[dict[str, str]],
) -> None:
    del experiment_summary_rows
    ws.sheet_view.showGridLines = False
    ws.merge_cells("A1:N1")
    ws["A1"] = "Research Console"
    ws["A1"].font = _TITLE_FONT
    ws["A1"].alignment = Alignment(horizontal="left")

    primary = next((row for row in strategy_metrics_rows if row["strategy_id"] == "f1_elasticnet_v1"), {})
    challenger = next((row for row in strategy_metrics_rows if row["strategy_id"] == "f2_structured_latent_factor_v1"), {})
    control = next((row for row in strategy_metrics_rows if row["strategy_id"] == "baseline_limit_up"), {})
    focus_rows = [
        row
        for row in strategy_metrics_rows
        if row["strategy_id"] in {"baseline_limit_up", "f1_elasticnet_v1", "f2_structured_latent_factor_v1"}
    ]

    _write_metric_card(ws, start_cell="A3", end_cell="C5", title="Project", value=project, fill=_CARD_FILL)
    _write_metric_card(
        ws,
        start_cell="D3",
        end_cell="F5",
        title="Mainline",
        value=_display_strategy_name("f1_elasticnet_v1", primary.get("name")) or "n/a",
        fill=_SUCCESS_FILL,
    )
    _write_metric_card(
        ws,
        start_cell="G3",
        end_cell="J5",
        title="Current blocker",
        value=_normalize_text(state.get("current_blocker")) or "n/a",
        fill=_CAUTION_FILL,
    )
    _write_metric_card(
        ws,
        start_cell="K3",
        end_cell="N5",
        title="Next action",
        value=_normalize_text(state.get("next_priority_action")) or "n/a",
        fill=_SUBTLE_FILL,
    )

    _write_metric_card(
        ws,
        start_cell="A7",
        end_cell="C9",
        title="F1 annualized / drawdown",
        value=f"{_fmt_pct(primary.get('annualized_return')) or 'n/a'} / {_fmt_pct(primary.get('max_drawdown')) or 'n/a'}",
        fill=_SUCCESS_FILL,
    )
    _write_metric_card(
        ws,
        start_cell="D7",
        end_cell="F9",
        title="F2 annualized / drawdown",
        value=f"{_fmt_pct(challenger.get('annualized_return')) or 'n/a'} / {_fmt_pct(challenger.get('max_drawdown')) or 'n/a'}",
        fill=_card_fill_for_status(_normalize_text(challenger.get("decision"))),
    )
    _write_metric_card(
        ws,
        start_cell="G7",
        end_cell="I9",
        title="Control annualized / drawdown",
        value=f"{_fmt_pct(control.get('annualized_return')) or 'n/a'} / {_fmt_pct(control.get('max_drawdown')) or 'n/a'}",
        fill=_NEUTRAL_FILL,
    )
    _write_metric_card(
        ws,
        start_cell="J7",
        end_cell="L9",
        title="Last export",
        value=_normalize_text(manifest.get("generated_at")) or "n/a",
        fill=_CARD_FILL,
    )
    _write_metric_card(
        ws,
        start_cell="M7",
        end_cell="N9",
        title="Mode",
        value=_normalize_text(manifest.get("workbook_mode")) or "n/a",
        fill=_CARD_FILL,
    )

    ws["A11"] = "Latest verified capability"
    ws["A11"].font = _SECTION_TITLE_FONT
    ws["A11"].fill = _HEADER_FILL
    ws["A11"].border = _BOX_BORDER
    ws.merge_cells("A11:G11")
    ws["A12"] = _normalize_text(state.get("last_verified_capability"))
    ws["A12"].fill = _SUBTLE_FILL
    ws["A12"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells("A12:G15")

    ws["I11"] = "Safe actions"
    ws["I11"].font = _SECTION_TITLE_FONT
    ws["I11"].fill = _HEADER_FILL
    ws["I11"].border = _BOX_BORDER
    ws.merge_cells("I11:N11")
    _button_cell(ws, "I12", label="Refresh Feed Pack", target=action_scripts["refresh_data_pack"])
    _button_cell(ws, "K12", label="Run research_audit", target=action_scripts["run_research_audit"])
    _button_cell(ws, "I13", label="Run agent_cycle --dry-run", target=action_scripts["run_agent_cycle_dry_run"])
    _button_cell(ws, "K13", label="Run f1_verify", target=action_scripts["run_f1_verify"])
    _button_cell(ws, "I14", label="Run f2_verify", target=action_scripts["run_f2_verify"])
    _button_cell(ws, "K14", label="Open artifacts folder", target=action_scripts["open_artifacts_dir"])
    _button_cell(ws, "I15", label="Open tracked memory folder", target=action_scripts["open_tracked_memory_dir"])
    _button_cell(ws, "K15", label="Open latest console", target=console_paths.open_latest_console_cmd)
    for cell_ref in ("I12", "K12", "I13", "K13", "I14", "K14", "I15", "K15"):
        ws[cell_ref].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws["A17"] = "Mainline vs challenger snapshot"
    ws["A17"].font = _SECTION_TITLE_FONT
    ws["A17"].fill = _HEADER_FILL
    ws["A17"].border = _BOX_BORDER
    ws.merge_cells("A17:I17")
    _append_strategy_metric_table(ws, start_row=18, rows=focus_rows)

    ws["A24"] = "Latest comparison chart"
    ws["A24"].font = _SECTION_TITLE_FONT
    ws["A24"].fill = _HEADER_FILL
    ws["A24"].border = _BOX_BORDER
    ws.merge_cells("A24:N24")
    if preview_plot_rows:
        _add_preview_image(ws, image_path=preview_plot_rows[0]["path"], anchor="A25", target_width=980)

    ws["A52"] = "Console note"
    ws["A52"].font = _SECTION_TITLE_FONT
    ws["A52"].fill = _HEADER_FILL
    ws["A52"].border = _BOX_BORDER
    ws.merge_cells("A52:N52")
    ws["A53"] = (
        "This home sheet is intentionally opinionated: it keeps only the current blocker, next action, "
        "safe operations, and the mainline-vs-challenger comparison. Detailed ledgers live on the other tabs."
    )
    ws["A53"].fill = _CAUTION_FILL
    ws["A53"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells("A53:N55")

    for row_idx, height in {1: 24, 3: 34, 7: 34, 12: 36, 13: 36, 14: 36, 15: 36}.items():
        ws.row_dimensions[row_idx].height = height
    for column, width in {
        "A": 16,
        "B": 16,
        "C": 16,
        "D": 16,
        "E": 18,
        "F": 18,
        "G": 18,
        "H": 18,
        "I": 18,
        "J": 18,
        "K": 18,
        "L": 18,
        "M": 18,
        "N": 18,
    }.items():
        ws.column_dimensions[column].width = width
    ws.freeze_panes = "A11"


def _write_strategies_sheet(
    ws: Worksheet,
    *,
    strategies_rows: list[dict[str, Any]],
    strategy_metrics_rows: list[dict[str, Any]],
) -> None:
    ws.sheet_view.showGridLines = False
    ws.merge_cells("A1:I1")
    ws["A1"] = "Strategies / 策略面板"
    ws["A1"].font = _TITLE_FONT
    ws["A1"].alignment = Alignment(horizontal="left")
    ws["A3"] = "核心指标对比"
    ws["A3"].font = _SECTION_TITLE_FONT
    ws["A3"].fill = _HEADER_FILL
    ws["A3"].border = _BOX_BORDER
    ws.merge_cells("A3:I3")
    header_row, end_row = _append_strategy_metric_table(ws, start_row=4, rows=strategy_metrics_rows)
    _add_strategy_comparison_chart(ws, data_start_row=header_row, data_end_row=end_row, anchor="K3")
    _write_table_sheet(
        ws,
        title="Narrative Strategy Ledger",
        rows=strategies_rows,
        columns=["strategy_id", "name", "track", "current_stage", "decision", "latest_result", "next_validation", "artifact_ref"],
        title_row=end_row + 2,
        start_row=end_row + 4,
    )
    ws.freeze_panes = "A4"


def _write_experiments_sheet(
    ws: Worksheet,
    *,
    experiments_rows: list[dict[str, Any]],
    experiment_summary_rows: list[dict[str, Any]],
) -> None:
    ws.sheet_view.showGridLines = False
    ws.merge_cells("A1:H1")
    ws["A1"] = "Experiments / 实验账本"
    ws["A1"].font = _TITLE_FONT
    ws["A1"].alignment = Alignment(horizontal="left")
    _add_experiment_summary_chart(ws, start_row=3, rows=experiment_summary_rows, anchor="D3")
    _write_table_sheet(
        ws,
        title="Recent Experiments",
        rows=experiments_rows,
        columns=["experiment_id", "timestamp", "mode", "strategy_candidate_id", "classification", "summary", "report_path"],
        title_row=15,
        start_row=17,
    )
    ws.freeze_panes = "A4"


def _write_artifacts_sheet(
    ws: Worksheet,
    *,
    artifacts_rows: list[dict[str, Any]],
    preview_plot_rows: list[dict[str, str]],
) -> None:
    ws.sheet_view.showGridLines = False
    ws.merge_cells("A1:H1")
    ws["A1"] = "Artifacts / 报告与图表"
    ws["A1"].font = _TITLE_FONT
    ws["A1"].alignment = Alignment(horizontal="left")
    _write_table_sheet(
        ws,
        title="Artifact Index",
        rows=artifacts_rows,
        columns=["artifact_type", "name", "path", "notes"],
        title_row=3,
        start_row=5,
    )
    preview_anchor_rows = [3, 26, 49]
    for index, preview in enumerate(preview_plot_rows[:3]):
        anchor_row = preview_anchor_rows[index]
        ws.cell(row=anchor_row, column=6, value=preview["label"]).font = _SECTION_TITLE_FONT
        ws.cell(row=anchor_row, column=6).fill = _HEADER_FILL
        ws.cell(row=anchor_row, column=6).border = _BOX_BORDER
        ws.merge_cells(start_row=anchor_row, start_column=6, end_row=anchor_row, end_column=10)
        _add_preview_image(ws, image_path=preview["path"], anchor=f"F{anchor_row + 1}", target_width=640)


def _write_notes(console_paths: ExcelConsolePaths, *, manifest: dict[str, Any]) -> Path:
    macro_status = str(manifest.get("macro_injection_status", "unknown"))
    workbook_mode = str(manifest.get("workbook_mode", "unknown"))
    text = "\n".join(
        [
            "# Excel Console Notes",
            "",
            f"- Generated at: {manifest.get('generated_at', '')}",
            f"- Workbook mode: {workbook_mode}",
            f"- Macro status: {macro_status}",
            "- Excel remains a read-first internal console. Python keeps the only source of truth.",
            "- The workbook uses launcher links under `actions/` for safe commands.",
            "- Embedded VBA was not injected in this MVP. If future runs enable VBProject access, the VBA template under `vba/` can be imported manually.",
            "",
            "## Freeze status",
            "- `apps/web` is now in feature freeze.",
            "- `dashboard/app.py` is now in feature freeze.",
            "- Delete the web surfaces only after the Excel console covers overview, experiment ledger, latest results, and the safe command set.",
        ]
    )
    return _write_text(console_paths.notes_path, text)


def _write_vba_template(console_paths: ExcelConsolePaths) -> Path:
    code = f"""Attribute VB_Name = "ResearchConsoleModule"
Option Explicit

Public Sub RefreshDataPack()
    Shell "{str(console_paths.actions_dir / 'refresh_data_pack.cmd').replace('"', '""')}", vbNormalFocus
End Sub

Public Sub RunResearchAudit()
    Shell "{str(console_paths.actions_dir / 'run_research_audit.cmd').replace('"', '""')}", vbNormalFocus
End Sub

Public Sub RunAgentCycleDryRun()
    Shell "{str(console_paths.actions_dir / 'run_agent_cycle_dry_run.cmd').replace('"', '""')}", vbNormalFocus
End Sub

Public Sub RunF1Verify()
    Shell "{str(console_paths.actions_dir / 'run_f1_verify.cmd').replace('"', '""')}", vbNormalFocus
End Sub

Public Sub RunF2Verify()
    Shell "{str(console_paths.actions_dir / 'run_f2_verify.cmd').replace('"', '""')}", vbNormalFocus
End Sub

Public Sub OpenArtifactsDir()
    Shell "{str(console_paths.actions_dir / 'open_artifacts_dir.cmd').replace('"', '""')}", vbNormalFocus
End Sub

Public Sub OpenTrackedMemoryDir()
    Shell "{str(console_paths.actions_dir / 'open_tracked_memory_dir.cmd').replace('"', '""')}", vbNormalFocus
End Sub
"""
    return _write_text(console_paths.vba_module_path, code)


def _write_cmd(path: Path, lines: list[str]) -> Path:
    return _write_text(path, "\n".join(lines))


def _quote_cmd_arg(value: str) -> str:
    if any(ch in value for ch in (' ', '&', '(', ')', '[', ']', '{', '}', '^', '=')):
        return _quote_cmd(value)
    return value


def _command_line(parts: Iterable[Path | str]) -> str:
    return " ".join(_quote_cmd_arg(str(part)) for part in parts)


def _write_action_scripts(
    *,
    project: str,
    repo_root: Path,
    python_executable: Path,
    console_paths: ExcelConsolePaths,
    workbook_output_path: Path,
) -> dict[str, Path]:
    open_latest = _write_cmd(
        console_paths.open_latest_console_cmd,
        [
            "@echo off",
            f"start \"\" {_quote_cmd(workbook_output_path)}",
        ],
    )

    def run_command_script(filename: str, *, cli_args: list[str]) -> Path:
        lines = [
            "@echo off",
            "setlocal",
            f"cd /d {_quote_cmd(repo_root)}",
            _command_line([python_executable, "-m", "quant_mvp", *cli_args]),
            "set CMD_EXIT=%ERRORLEVEL%",
            _command_line([python_executable, "-m", "quant_mvp", "excel_export", "--project", project]),
            f"call {_quote_cmd(open_latest)}",
            "echo.",
            "pause",
            "exit /b %CMD_EXIT%",
        ]
        return _write_cmd(console_paths.actions_dir / filename, lines)

    refresh_data_pack = _write_cmd(
        console_paths.actions_dir / "refresh_data_pack.cmd",
        [
            "@echo off",
            "setlocal",
            f"cd /d {_quote_cmd(repo_root)}",
            _command_line([python_executable, "-m", "quant_mvp", "excel_export", "--project", project]),
            "set CMD_EXIT=%ERRORLEVEL%",
            f"call {_quote_cmd(open_latest)}",
            "echo.",
            "pause",
            "exit /b %CMD_EXIT%",
        ],
    )
    run_research_audit = run_command_script(
        "run_research_audit.cmd",
        cli_args=["research_audit", "--project", project],
    )
    run_agent_cycle_dry_run = run_command_script(
        "run_agent_cycle_dry_run.cmd",
        cli_args=["agent_cycle", "--project", project, "--dry-run"],
    )
    run_f1_verify = run_command_script(
        "run_f1_verify.cmd",
        cli_args=["f1_verify", "--project", project],
    )
    run_f2_verify = run_command_script(
        "run_f2_verify.cmd",
        cli_args=["f2_verify", "--project", project],
    )
    open_artifacts_dir = _write_cmd(
        console_paths.actions_dir / "open_artifacts_dir.cmd",
        [
            "@echo off",
            f"explorer {_quote_cmd(repo_root / 'artifacts' / 'projects' / project)}",
        ],
    )
    open_tracked_memory_dir = _write_cmd(
        console_paths.actions_dir / "open_tracked_memory_dir.cmd",
        [
            "@echo off",
            f"explorer {_quote_cmd(repo_root / 'memory' / 'projects' / project)}",
        ],
    )
    return {
        "refresh_data_pack": refresh_data_pack,
        "run_research_audit": run_research_audit,
        "run_agent_cycle_dry_run": run_agent_cycle_dry_run,
        "run_f1_verify": run_f1_verify,
        "run_f2_verify": run_f2_verify,
        "open_artifacts_dir": open_artifacts_dir,
        "open_tracked_memory_dir": open_tracked_memory_dir,
        "open_latest_console": open_latest,
    }


def _build_workbook(
    *,
    workbook_path: Path,
    project: str,
    state: dict[str, Any],
    manifest: dict[str, Any],
    action_scripts: dict[str, Path],
    console_paths: ExcelConsolePaths,
    overview_rows: list[dict[str, Any]],
    strategies_rows: list[dict[str, Any]],
    strategy_metrics_rows: list[dict[str, Any]],
    experiment_summary_rows: list[dict[str, Any]],
    experiments_rows: list[dict[str, Any]],
    runs_rows: list[dict[str, Any]],
    artifacts_rows: list[dict[str, Any]],
) -> Path:
    workbook = Workbook()
    workbook.remove(workbook.active)
    control_ws = workbook.create_sheet(WORKSHEET_NAMES[0])
    overview_ws = workbook.create_sheet(WORKSHEET_NAMES[1])
    strategies_ws = workbook.create_sheet(WORKSHEET_NAMES[2])
    experiments_ws = workbook.create_sheet(WORKSHEET_NAMES[3])
    runs_ws = workbook.create_sheet(WORKSHEET_NAMES[4])
    artifacts_ws = workbook.create_sheet(WORKSHEET_NAMES[5])

    _write_control_sheet(
        control_ws,
        project=project,
        state=state,
        manifest=manifest,
        action_scripts=action_scripts,
        console_paths=console_paths,
        strategy_metrics_rows=strategy_metrics_rows,
        experiment_summary_rows=experiment_summary_rows,
    )
    _write_overview_sheet(
        overview_ws,
        overview_rows,
        strategy_metrics_rows=strategy_metrics_rows,
        experiment_summary_rows=experiment_summary_rows,
    )
    _write_strategies_sheet(
        strategies_ws,
        strategies_rows=strategies_rows,
        strategy_metrics_rows=strategy_metrics_rows,
    )
    _write_experiments_sheet(
        experiments_ws,
        experiments_rows=experiments_rows,
        experiment_summary_rows=experiment_summary_rows,
    )
    _write_table_sheet(
        runs_ws,
        title="Runs",
        rows=runs_rows,
        columns=["run_id", "kind", "status", "started_at", "finished_at", "summary", "artifact_path"],
    )
    _write_artifacts_sheet(
        artifacts_ws,
        artifacts_rows=artifacts_rows,
        preview_plot_rows=_preview_plot_rows(state),
    )
    staging_dir = workbook_path.parent / "_staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    temp_xlsx = staging_dir / f"{workbook_path.stem}__staging.xlsx"
    workbook.save(temp_xlsx)
    if workbook_path.suffix.lower() == ".xlsm":
        try:
            _convert_xlsx_to_xlsm(temp_xlsx, workbook_path)
        finally:
            temp_xlsx.unlink(missing_ok=True)
    else:
        shutil.move(str(temp_xlsx), str(workbook_path))
    return workbook_path


def _write_manifest(console_paths: ExcelConsolePaths, manifest: dict[str, Any]) -> Path:
    console_paths.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    console_paths.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).rstrip() + "\n",
        encoding="utf-8",
    )
    return console_paths.manifest_path


def run_excel_export(
    project: str,
    *,
    config_path: Path | None = None,
    repo_root: Path | None = None,
    probe_vba: bool = True,
) -> dict[str, Any]:
    root = find_repo_root(repo_root)
    requested_config_path = ""
    if config_path is not None:
        resolved_config = config_path.resolve()
        if not resolved_config.exists():
            raise FileNotFoundError(f"Config path not found: {resolved_config}")
        requested_config_path = str(resolved_config)
    bootstrap_memory_files(project, repo_root=root)
    paths, state = load_machine_state(project, repo_root=root)
    console_paths = _excel_console_paths(paths)
    _ensure_excel_dirs(console_paths)

    vba_status = (
        _probe_excel_vba_status()
        if probe_vba
        else {
            "excel_com_available": False,
            "vbproject_access": False,
            "status": "probe_skipped",
            "detail": "Probe skipped for deterministic or test execution.",
        }
    )
    workbook_mode = (
        "embedded_vba_ready"
        if bool(vba_status.get("vbproject_access"))
        else "launcher_links_fallback"
    )

    overview_rows = _overview_rows(state, workbook_mode=workbook_mode, workbook_path=console_paths.workbook_path)
    strategies_rows = _strategies_rows(state)
    strategy_metrics_rows = _strategy_metrics_rows(state)
    experiment_summary_rows = _experiment_summary_rows(paths)
    experiments_rows = _experiments_rows(paths)
    runs_rows = _runs_rows(paths)

    feed_files = {
        "overview": _write_csv(
            console_paths.feed_dir / "overview.csv",
            overview_rows,
            ["section", "key", "value", "display_order"],
        ),
        "strategies": _write_csv(
            console_paths.feed_dir / "strategies.csv",
            strategies_rows,
            ["strategy_id", "name", "track", "current_stage", "decision", "latest_result", "next_validation", "artifact_ref"],
        ),
        "strategy_metrics": _write_csv(
            console_paths.feed_dir / "strategy_metrics.csv",
            strategy_metrics_rows,
            [
                "strategy_id",
                "name",
                "track",
                "decision",
                "classification",
                "annualized_return",
                "max_drawdown",
                "sharpe_ratio",
                "calmar_ratio",
                "turnover",
                "win_rate",
                "artifact_ref",
            ],
        ),
        "experiments": _write_csv(
            console_paths.feed_dir / "experiments.csv",
            experiments_rows,
            ["experiment_id", "timestamp", "mode", "strategy_candidate_id", "classification", "summary", "report_path"],
        ),
        "experiment_summary": _write_csv(
            console_paths.feed_dir / "experiment_summary.csv",
            experiment_summary_rows,
            ["classification", "count"],
        ),
        "runs": _write_csv(
            console_paths.feed_dir / "runs.csv",
            runs_rows,
            ["run_id", "kind", "status", "started_at", "finished_at", "summary", "artifact_path"],
        ),
    }
    manifest_stub = {
        "project": paths.project,
        "generated_at": _utc_now(),
        "feed_version": FEED_VERSION,
        "workbook_mode": workbook_mode,
        "macro_injection_status": str(vba_status.get("status", "unknown")),
        "macro_probe": vba_status,
        "primary_workbook_path": str(console_paths.workbook_path),
        "requested_config_path": requested_config_path,
        "config_override_mode": "tracked_truth_export_only",
    }
    artifacts_rows = _artifacts_rows(paths, state, console_paths, manifest_stub)
    feed_files["artifacts"] = _write_csv(
        console_paths.feed_dir / "artifacts.csv",
        artifacts_rows,
        ["artifact_type", "name", "path", "notes"],
    )

    action_scripts = _write_action_scripts(
        project=paths.project,
        repo_root=root,
        python_executable=Path(sys.executable),
        console_paths=console_paths,
        workbook_output_path=console_paths.workbook_path,
    )
    _write_vba_template(console_paths)

    workbook_output_path = console_paths.workbook_path
    workbook_write_status = "primary_workbook_updated"
    try:
        _build_workbook(
            workbook_path=console_paths.workbook_path,
            project=paths.project,
            state=state,
            manifest={**manifest_stub, "effective_workbook_path": str(console_paths.workbook_path)},
            action_scripts=action_scripts,
            console_paths=console_paths,
            overview_rows=overview_rows,
            strategies_rows=strategies_rows,
            strategy_metrics_rows=strategy_metrics_rows,
            experiment_summary_rows=experiment_summary_rows,
            experiments_rows=experiments_rows,
            runs_rows=runs_rows,
            artifacts_rows=artifacts_rows,
        )
    except PermissionError:
        workbook_output_path = console_paths.root / f"ResearchConsole_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.xlsm"
        workbook_write_status = "primary_workbook_locked_wrote_timestamped_copy"
        _build_workbook(
            workbook_path=workbook_output_path,
            project=paths.project,
            state=state,
            manifest={**manifest_stub, "effective_workbook_path": str(workbook_output_path)},
            action_scripts=action_scripts,
            console_paths=console_paths,
            overview_rows=overview_rows,
            strategies_rows=strategies_rows,
            strategy_metrics_rows=strategy_metrics_rows,
            experiment_summary_rows=experiment_summary_rows,
            experiments_rows=experiments_rows,
            runs_rows=runs_rows,
            artifacts_rows=artifacts_rows,
        )

    action_scripts = _write_action_scripts(
        project=paths.project,
        repo_root=root,
        python_executable=Path(sys.executable),
        console_paths=console_paths,
        workbook_output_path=workbook_output_path,
    )

    manifest = {
        "project": paths.project,
        "generated_at": _utc_now(),
        "feed_version": FEED_VERSION,
        "workbook_mode": workbook_mode,
        "macro_injection_status": str(vba_status.get("status", "unknown")),
        "macro_probe": vba_status,
        "primary_workbook_path": str(console_paths.workbook_path),
        "requested_config_path": requested_config_path,
        "config_override_mode": "tracked_truth_export_only",
        "effective_workbook_path": str(workbook_output_path),
        "workbook_write_status": workbook_write_status,
        "feed_files": {key: str(value) for key, value in feed_files.items()},
        "action_scripts": {key: str(value) for key, value in action_scripts.items()},
        "notes_path": str(console_paths.notes_path),
        "vba_module_path": str(console_paths.vba_module_path),
        "web_freeze_status": "frozen_until_excel_mvp_acceptance",
        "safe_actions": [
            "refresh_data_pack",
            "research_audit",
            "agent_cycle_dry_run",
            "f1_verify",
            "f2_verify",
            "open_artifacts_dir",
            "open_tracked_memory_dir",
        ],
    }
    artifacts_rows = _artifacts_rows(paths, state, console_paths, manifest)
    feed_files["artifacts"] = _write_csv(
        console_paths.feed_dir / "artifacts.csv",
        artifacts_rows,
        ["artifact_type", "name", "path", "notes"],
    )
    _write_manifest(console_paths, manifest)
    _write_notes(console_paths, manifest=manifest)
    _build_workbook(
        workbook_path=workbook_output_path,
        project=paths.project,
        state=state,
        manifest=manifest,
        action_scripts=action_scripts,
        console_paths=console_paths,
        overview_rows=overview_rows,
        strategies_rows=strategies_rows,
        strategy_metrics_rows=strategy_metrics_rows,
        experiment_summary_rows=experiment_summary_rows,
        experiments_rows=experiments_rows,
        runs_rows=runs_rows,
        artifacts_rows=artifacts_rows,
    )

    return {
        "project": paths.project,
        "excel_root": str(console_paths.root),
        "workbook_path": str(workbook_output_path),
        "manifest_path": str(console_paths.manifest_path),
        "workbook_mode": workbook_mode,
        "macro_injection_status": manifest["macro_injection_status"],
        "feed_files": {key: str(value) for key, value in feed_files.items()},
        "action_scripts": {key: str(value) for key, value in action_scripts.items()},
    }
