from __future__ import annotations

import csv
import json
import math
import shutil
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from ..config import load_config
from ..db import get_conn, table_exists
from ..manifest import update_run_manifest
from ..project import resolve_project_paths
from ..universe import save_universe_codes

ATTEMPT_STATUS_FILE = "bars_attempt_status.json"

COVERED_VALIDATED = "covered_validated"
MISSING_RAW_TRANSIENT_FAILURE = "missing_raw_transient_failure"
MISSING_RAW_NEVER_ATTEMPTED = "missing_raw_never_attempted"
VALIDATION_REJECTION = "validation_rejection"
ANOMALOUS_STATE = "anomalous_state"

_TRANSIENT_FAILURE_STATUSES = {"failed", "transient_failure", "network_error", "timeout"}
_ANOMALOUS_ATTEMPT_STATUSES = {"empty_response", "success_no_rows", "unknown"}


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _normalize_codes(codes: list[str]) -> list[str]:
    return sorted({str(code).zfill(6) for code in codes if str(code).strip()})


def _chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[idx : idx + size] for idx in range(0, len(items), size)]


def _json_dump(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2).rstrip() + "\n", encoding="utf-8")
    return path


def load_bars_attempt_status(meta_dir: Path) -> dict[str, dict[str, Any]]:
    path = meta_dir / ATTEMPT_STATUS_FILE
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for code, item in payload.items():
        if not isinstance(item, dict):
            continue
        normalized[str(code).zfill(6)] = dict(item)
    return normalized


def save_bars_attempt_status(meta_dir: Path, payload: dict[str, dict[str, Any]]) -> Path:
    normalized: dict[str, dict[str, Any]] = {}
    for code, item in payload.items():
        normalized[str(code).zfill(6)] = dict(item)
    return _json_dump(meta_dir / ATTEMPT_STATUS_FILE, normalized)


@dataclass(frozen=True)
class CoverageGapSymbolEntry:
    symbol: str
    classification: str
    raw_rows: int
    validated_rows: int
    validated_last_date: str | None
    attempt_status: str
    last_error: str
    attempt_count: int
    last_success_end_date: str | None
    eligible_refreeze: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CoverageGapDecision:
    decision: str
    decision_style: str
    required_symbols_for_readiness: int
    covered_symbols: int
    transient_recoverable_symbols: int
    recoverable_symbols: int
    eligible_refreeze_symbols: int
    old_universe_size: int
    new_universe_size: int | None
    auto_refreeze_enabled: bool
    auto_refreeze_applied: bool
    decision_reason: str
    next_action: str
    artifact_paths: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CoverageGapLedger:
    project: str
    frequency: str
    generated_at: str
    current_universe_size: int
    min_coverage_ratio: float
    eligibility_min_bars: int
    required_end_date: str | None
    classification_counts: dict[str, int]
    entries: list[CoverageGapSymbolEntry]
    decision: CoverageGapDecision

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["entries"] = [item.to_dict() for item in self.entries]
        payload["decision"] = self.decision.to_dict()
        return payload


@dataclass(frozen=True)
class RefreezeResult:
    applied: bool
    old_universe_size: int
    new_universe_size: int
    universe_path: Path
    symbols_path: Path
    pre_refreeze_universe_path: Path
    pre_refreeze_symbols_path: Path
    snapshot_universe_path: Path
    snapshot_symbols_path: Path
    config_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "applied": self.applied,
            "old_universe_size": self.old_universe_size,
            "new_universe_size": self.new_universe_size,
            "universe_path": str(self.universe_path),
            "symbols_path": str(self.symbols_path),
            "pre_refreeze_universe_path": str(self.pre_refreeze_universe_path),
            "pre_refreeze_symbols_path": str(self.pre_refreeze_symbols_path),
            "snapshot_universe_path": str(self.snapshot_universe_path),
            "snapshot_symbols_path": str(self.snapshot_symbols_path),
            "config_path": str(self.config_path),
        }


def _table_symbol_stats(
    *,
    db_path: Path,
    table_name: str,
    freq: str,
    codes: list[str],
) -> dict[str, dict[str, Any]]:
    normalized = _normalize_codes(codes)
    if not normalized:
        return {}
    stats = {
        code: {"rows": 0, "last_date": None}
        for code in normalized
    }
    with get_conn(db_path) as conn:
        if not table_exists(conn, table_name):
            return stats
        for chunk in _chunked(normalized, 800):
            placeholders = ",".join(["?"] * len(chunk))
            rows = conn.execute(
                f"""
                SELECT symbol, COUNT(*) AS rows_count, MAX(datetime) AS last_date
                FROM {table_name}
                WHERE freq=? AND symbol IN ({placeholders})
                GROUP BY symbol
                """,
                [freq, *chunk],
            ).fetchall()
            for symbol, rows_count, last_date in rows:
                code = str(symbol).zfill(6)
                stats[code] = {
                    "rows": int(rows_count or 0),
                    "last_date": str(last_date) if last_date else None,
                }
    return stats


def _policy_value(cfg: Mapping[str, Any], key: str, default: Any) -> Any:
    policy = cfg.get("coverage_gap_policy", {}) if isinstance(cfg, Mapping) else {}
    if not isinstance(policy, Mapping):
        return default
    return policy.get(key, default)


def build_coverage_gap_ledger(
    *,
    project: str,
    db_path: Path,
    freq: str,
    universe_codes: list[str],
    cfg: Mapping[str, Any],
    meta_dir: Path,
    data_quality_cfg: Mapping[str, Any] | None = None,
) -> CoverageGapLedger:
    normalized = _normalize_codes(universe_codes)
    quality_cfg = data_quality_cfg or {}
    raw_table = str(quality_cfg.get("source_table", "bars"))
    validated_table = str(quality_cfg.get("clean_table", "bars_clean"))
    raw_stats = _table_symbol_stats(db_path=db_path, table_name=raw_table, freq=freq, codes=normalized)
    validated_stats = _table_symbol_stats(db_path=db_path, table_name=validated_table, freq=freq, codes=normalized)
    attempt_status = load_bars_attempt_status(meta_dir)

    min_coverage_ratio = float(cfg.get("research_readiness", {}).get("min_coverage_ratio", 0.95))
    eligibility_min_bars = int(_policy_value(cfg, "eligibility_min_bars", cfg.get("min_bars", 1)) or 1)
    required_end_date = _policy_value(cfg, "required_end_date", cfg.get("end_date"))
    auto_refreeze = bool(_policy_value(cfg, "auto_refreeze", True))
    decision_style = str(_policy_value(cfg, "decision_style", "conservative"))

    entries: list[CoverageGapSymbolEntry] = []
    counts = {
        COVERED_VALIDATED: 0,
        MISSING_RAW_TRANSIENT_FAILURE: 0,
        MISSING_RAW_NEVER_ATTEMPTED: 0,
        VALIDATION_REJECTION: 0,
        ANOMALOUS_STATE: 0,
    }

    for code in normalized:
        raw_row_count = int(raw_stats.get(code, {}).get("rows", 0) or 0)
        validated_row_count = int(validated_stats.get(code, {}).get("rows", 0) or 0)
        validated_last_date = validated_stats.get(code, {}).get("last_date")
        attempt = attempt_status.get(code, {})
        status = str(attempt.get("status", "") or "").strip().lower()
        last_error = str(attempt.get("last_error", "") or "").strip()
        attempt_count = int(attempt.get("attempt_count", 0) or 0)
        last_success_end_date = attempt.get("last_success_end_date")

        if validated_row_count > 0 and raw_row_count <= 0:
            classification = ANOMALOUS_STATE
        elif validated_row_count > 0:
            classification = COVERED_VALIDATED
        elif raw_row_count > 0:
            classification = VALIDATION_REJECTION
        elif status in _TRANSIENT_FAILURE_STATUSES or last_error:
            classification = MISSING_RAW_TRANSIENT_FAILURE
        elif status in _ANOMALOUS_ATTEMPT_STATUSES:
            classification = ANOMALOUS_STATE
        else:
            classification = MISSING_RAW_NEVER_ATTEMPTED

        eligible_refreeze = (
            classification == COVERED_VALIDATED
            and validated_row_count >= eligibility_min_bars
            and (not required_end_date or (validated_last_date or "") >= str(required_end_date))
        )
        counts[classification] += 1
        entries.append(
            CoverageGapSymbolEntry(
                symbol=code,
                classification=classification,
                raw_rows=raw_row_count,
                validated_rows=validated_row_count,
                validated_last_date=validated_last_date,
                attempt_status=status or "none",
                last_error=last_error,
                attempt_count=attempt_count,
                last_success_end_date=str(last_success_end_date) if last_success_end_date else None,
                eligible_refreeze=eligible_refreeze,
            ),
        )

    required_symbols = int(math.ceil(min_coverage_ratio * len(normalized))) if normalized else 0
    covered_symbols = counts[COVERED_VALIDATED]
    transient_recoverable = counts[MISSING_RAW_TRANSIENT_FAILURE]
    recoverable_symbols = covered_symbols + transient_recoverable
    eligible_refreeze_symbols = sum(1 for item in entries if item.eligible_refreeze)
    if recoverable_symbols >= required_symbols:
        decision = "expand_bars"
        reason = (
            f"Recoverable symbols {recoverable_symbols} meet the readiness floor {required_symbols}; "
            "keep the frozen universe and retry transient failures first."
        )
        next_action = (
            f"Retry transient bar recovery for {transient_recoverable} symbols listed in the coverage-gap ledger "
            "before changing the frozen universe."
        )
    else:
        decision = "refreeze"
        reason = (
            f"Recoverable symbols {recoverable_symbols} do not meet the readiness floor {required_symbols}; "
            "the current frozen universe is not honestly recoverable under the conservative policy."
        )
        next_action = (
            "Auto-refreeze to the validated eligible subset if enabled; otherwise refreeze the universe manually "
            "before trusting promotion-grade research."
        )
    return CoverageGapLedger(
        project=project,
        frequency=freq,
        generated_at=_utc_now(),
        current_universe_size=len(normalized),
        min_coverage_ratio=min_coverage_ratio,
        eligibility_min_bars=eligibility_min_bars,
        required_end_date=str(required_end_date) if required_end_date else None,
        classification_counts=counts,
        entries=entries,
        decision=CoverageGapDecision(
            decision=decision,
            decision_style=decision_style,
            required_symbols_for_readiness=required_symbols,
            covered_symbols=covered_symbols,
            transient_recoverable_symbols=transient_recoverable,
            recoverable_symbols=recoverable_symbols,
            eligible_refreeze_symbols=eligible_refreeze_symbols,
            old_universe_size=len(normalized),
            new_universe_size=None,
            auto_refreeze_enabled=auto_refreeze,
            auto_refreeze_applied=False,
            decision_reason=reason,
            next_action=next_action,
            artifact_paths={},
        ),
    )


def write_coverage_gap_artifacts(
    *,
    meta_dir: Path,
    ledger: CoverageGapLedger,
) -> tuple[Path, Path, Path]:
    meta_dir.mkdir(parents=True, exist_ok=True)
    json_path = meta_dir / "coverage_gap_ledger.json"
    csv_path = meta_dir / "coverage_gap_by_symbol.csv"
    markdown_path = meta_dir / "COVERAGE_GAP_LEDGER.md"

    json_path.write_text(json.dumps(ledger.to_dict(), ensure_ascii=False, indent=2).rstrip() + "\n", encoding="utf-8")

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "symbol",
                "classification",
                "raw_rows",
                "validated_rows",
                "validated_last_date",
                "attempt_status",
                "last_error",
                "attempt_count",
                "last_success_end_date",
                "eligible_refreeze",
            ],
        )
        writer.writeheader()
        for entry in ledger.entries:
            writer.writerow(entry.to_dict())

    lines = [
        "# Coverage Gap Ledger",
        "",
        f"- project: {ledger.project}",
        f"- frequency: {ledger.frequency}",
        f"- generated_at: {ledger.generated_at}",
        f"- current_universe_size: {ledger.current_universe_size}",
        f"- min_coverage_ratio: {ledger.min_coverage_ratio:.4f}",
        f"- required_symbols_for_readiness: {ledger.decision.required_symbols_for_readiness}",
        f"- covered_symbols: {ledger.decision.covered_symbols}",
        f"- transient_recoverable_symbols: {ledger.decision.transient_recoverable_symbols}",
        f"- eligible_refreeze_symbols: {ledger.decision.eligible_refreeze_symbols}",
        f"- decision: {ledger.decision.decision}",
        f"- decision_reason: {ledger.decision.decision_reason}",
        "",
        "## Classification Counts",
    ]
    lines.extend(f"- {key}: {value}" for key, value in ledger.classification_counts.items())
    lines.extend(["", "## Next Action", f"- {ledger.decision.next_action}", "", "## Sample Gaps"])
    sample = [item for item in ledger.entries if item.classification != COVERED_VALIDATED][:10]
    if sample:
        lines.extend(
            f"- {item.symbol}: {item.classification} (attempt_status={item.attempt_status}, last_error={item.last_error or 'none'})"
            for item in sample
        )
    else:
        lines.append("- No gaps remain.")
    markdown_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return markdown_path, json_path, csv_path


def ledger_with_artifact_paths(
    ledger: CoverageGapLedger,
    *,
    markdown_path: Path,
    json_path: Path,
    csv_path: Path,
    refreeze_result: RefreezeResult | None = None,
) -> CoverageGapLedger:
    decision = CoverageGapDecision(
        **{
            **ledger.decision.to_dict(),
            "artifact_paths": {
                "markdown_path": str(markdown_path),
                "json_path": str(json_path),
                "csv_path": str(csv_path),
                **({"refreeze": refreeze_result.to_dict()} if refreeze_result else {}),
            },
            "new_universe_size": refreeze_result.new_universe_size if refreeze_result else ledger.decision.new_universe_size,
            "auto_refreeze_applied": bool(refreeze_result and refreeze_result.applied),
        },
    )
    return CoverageGapLedger(
        project=ledger.project,
        frequency=ledger.frequency,
        generated_at=ledger.generated_at,
        current_universe_size=ledger.current_universe_size,
        min_coverage_ratio=ledger.min_coverage_ratio,
        eligibility_min_bars=ledger.eligibility_min_bars,
        required_end_date=ledger.required_end_date,
        classification_counts=dict(ledger.classification_counts),
        entries=list(ledger.entries),
        decision=decision,
    )


def _read_symbols_rows(symbols_path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not symbols_path.exists():
        return [], ["code", "name", "is_st", "board"]
    with open(symbols_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
        fieldnames = list(reader.fieldnames or ["code", "name", "is_st", "board"])
    return rows, fieldnames


def _write_symbols_rows(symbols_path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> Path:
    symbols_path.parent.mkdir(parents=True, exist_ok=True)
    with open(symbols_path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return symbols_path


def apply_auto_refreeze(
    *,
    project: str,
    config_path: Path,
    ledger: CoverageGapLedger,
) -> RefreezeResult | None:
    if ledger.decision.decision != "refreeze" or not ledger.decision.auto_refreeze_enabled:
        return None

    eligible_codes = sorted(item.symbol for item in ledger.entries if item.eligible_refreeze)
    if not eligible_codes:
        return None

    paths = resolve_project_paths(project)
    universe_path = paths.universe_path
    symbols_path = paths.meta_dir / "symbols.csv"
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    pre_refreeze_universe_path = paths.meta_dir / f"pre_refreeze_universe_codes_{timestamp}.txt"
    pre_refreeze_symbols_path = paths.meta_dir / f"pre_refreeze_symbols_{timestamp}.csv"
    snapshot_universe_path = paths.meta_dir / f"refreeze_universe_codes_{timestamp}.txt"
    snapshot_symbols_path = paths.meta_dir / f"refreeze_symbols_{timestamp}.csv"

    old_universe = [line.strip() for line in universe_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    universe_path.parent.mkdir(parents=True, exist_ok=True)
    pre_refreeze_universe_path.write_text("\n".join(old_universe).rstrip() + "\n", encoding="utf-8")
    if symbols_path.exists():
        shutil.copyfile(symbols_path, pre_refreeze_symbols_path)
    else:
        pre_refreeze_symbols_path.write_text("", encoding="utf-8")

    rows, fieldnames = _read_symbols_rows(symbols_path)
    row_by_code = {str(row.get("code", "")).zfill(6): row for row in rows}
    new_rows: list[dict[str, str]] = []
    for code in eligible_codes:
        row = dict(row_by_code.get(code, {}))
        row.setdefault("code", code)
        row.setdefault("name", "")
        row.setdefault("is_st", "False")
        row.setdefault("board", "mainboard")
        row["code"] = code
        new_rows.append(row)

    snapshot_universe_path.write_text("\n".join(eligible_codes).rstrip() + "\n", encoding="utf-8")
    _write_symbols_rows(snapshot_symbols_path, new_rows, fieldnames)

    save_universe_codes(project=project, codes=eligible_codes)
    _write_symbols_rows(symbols_path, new_rows, fieldnames)

    file_config = json.loads(config_path.read_text(encoding="utf-8"))
    file_config["universe_size_target"] = len(eligible_codes)
    config_path.write_text(json.dumps(file_config, ensure_ascii=False, indent=2).rstrip() + "\n", encoding="utf-8")

    return RefreezeResult(
        applied=True,
        old_universe_size=len(old_universe),
        new_universe_size=len(eligible_codes),
        universe_path=universe_path,
        symbols_path=symbols_path,
        pre_refreeze_universe_path=pre_refreeze_universe_path,
        pre_refreeze_symbols_path=pre_refreeze_symbols_path,
        snapshot_universe_path=snapshot_universe_path,
        snapshot_symbols_path=snapshot_symbols_path,
        config_path=config_path,
    )


def write_coverage_gap_decision_to_manifest(
    *,
    project: str,
    ledger: CoverageGapLedger,
    symbols_source: str | None = None,
) -> Path:
    updates: dict[str, Any] = {
        "coverage_gap_decision": {
            "decision": ledger.decision.decision,
            "decision_style": ledger.decision.decision_style,
            "required_symbols_for_readiness": ledger.decision.required_symbols_for_readiness,
            "covered_symbols": ledger.decision.covered_symbols,
            "transient_recoverable_symbols": ledger.decision.transient_recoverable_symbols,
            "eligible_refreeze_symbols": ledger.decision.eligible_refreeze_symbols,
            "old_universe_size": ledger.decision.old_universe_size,
            "new_universe_size": ledger.decision.new_universe_size,
            "auto_refreeze_enabled": ledger.decision.auto_refreeze_enabled,
            "auto_refreeze_applied": ledger.decision.auto_refreeze_applied,
            "decision_reason": ledger.decision.decision_reason,
            "artifact_paths": ledger.decision.artifact_paths,
        },
    }
    if symbols_source:
        updates["symbols_source"] = symbols_source
    return update_run_manifest(project, updates)


def append_decision_log_entry(*, root: Path, line: str) -> Path:
    path = root / "docs" / "DECISION_LOG.md"
    if not path.exists():
        path.write_text("# Decision Log\n\n", encoding="utf-8")
    text = path.read_text(encoding="utf-8")
    if line in text:
        return path
    marker = "## 2026-03-25"
    entry = f"- {line}\n"
    if marker in text:
        updated = text.replace(marker, f"{marker}\n{entry}", 1)
    else:
        updated = text.rstrip() + f"\n\n## {datetime.now().date().isoformat()}\n{entry}"
    path.write_text(updated, encoding="utf-8")
    return path


def reload_project_config(project: str, config_path: Path) -> tuple[dict[str, Any], Any]:
    return load_config(project, config_path=config_path)
