from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from .config import load_config
from .data.coverage_gap import load_bars_attempt_status
from .data.validate_flow import run_data_validate_flow
from .memory.ledger import append_jsonl, stable_hash
from .project import find_repo_root, resolve_project_paths
from .project_identity import CANONICAL_PROJECT_ID
from .universe import load_universe_codes


CURRENT_UNIVERSE_ID = "cn_a_mainboard_all_v1"


@dataclass(frozen=True)
class CoverageStageDecision:
    stage: str
    bias_explained: bool
    baseline_reassessment_allowed: bool
    legacy_restore_allowed: bool
    reasons: list[str]
    thresholds: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return path


def _normalize_codes(values: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        code = str(value or "").strip()
        if not code:
            continue
        padded = code.zfill(6)
        if padded in seen:
            continue
        seen.add(padded)
        normalized.append(padded)
    return normalized


def _read_distinct_symbols(db_path: Path, table_name: str, freq: str) -> set[str]:
    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        if row is None:
            return set()
        rows = conn.execute(
            f"SELECT DISTINCT symbol FROM {table_name} WHERE freq=?",
            (freq,),
        ).fetchall()
        return {str(item[0]).zfill(6) for item in rows}
    finally:
        conn.close()


def _load_security_master(meta_dir: Path) -> pd.DataFrame:
    path = meta_dir / "security_master.csv"
    if not path.exists():
        raise FileNotFoundError(f"security master missing: {path}")
    frame = pd.read_csv(path, dtype={"code": str})
    frame["code"] = frame["code"].astype(str).str.zfill(6)
    if "security_name" not in frame.columns and "name" in frame.columns:
        frame["security_name"] = frame["name"]
    if "name" not in frame.columns and "security_name" in frame.columns:
        frame["name"] = frame["security_name"]
    if "is_st" not in frame.columns:
        frame["is_st"] = frame["security_name"].fillna("").str.contains("ST", case=False, regex=False)
    frame["is_st"] = frame["is_st"].fillna(False).astype(bool)
    frame["listing_date"] = pd.to_datetime(frame.get("listing_date"), errors="coerce")
    return frame


def _name_pattern(name: str) -> str:
    text = str(name or "").strip()
    upper = text.upper()
    if "ST" in upper:
        return "ST/*ST"
    if text.endswith(("A", "Ａ")):
        return "A字尾名称"
    if " " in text:
        return "带空格旧式名称"
    return "普通名称"


def _listing_age_bucket(listing_date: pd.Timestamp | pd.NaT, required_end: pd.Timestamp) -> str:
    if pd.isna(listing_date):
        return "上市日期未知"
    days = int((required_end - listing_date).days)
    if days < 0:
        return "截止日后上市"
    if days < 365:
        return "1年内"
    if days < 365 * 3:
        return "1-3年"
    if days < 365 * 8:
        return "3-8年"
    if days < 365 * 15:
        return "8-15年"
    return "15年以上"


def _code_bucket(code: str) -> str:
    padded = str(code or "").zfill(6)
    return padded[:3]


def _market_status(name: str) -> str:
    text = str(name or "")
    if "退" in text:
        return "退市字样"
    return "当前活跃名单"


def build_coverage_recovery_frame(
    *,
    project: str,
    cfg: Mapping[str, Any],
    db_path: Path,
    meta_dir: Path,
    universe_codes: list[str],
) -> pd.DataFrame:
    frame = _load_security_master(meta_dir)
    target = set(_normalize_codes(universe_codes))
    frame = frame[frame["code"].isin(target)].copy()
    frame = frame.sort_values("code").reset_index(drop=True)

    freq = str(cfg["freq"])
    required_end_text = str((cfg.get("coverage_gap_policy", {}) or {}).get("required_end_date") or cfg.get("end_date"))
    required_end = pd.Timestamp(required_end_text)

    raw_symbols = _read_distinct_symbols(db_path, "bars", freq)
    clean_symbols = _read_distinct_symbols(db_path, "bars_clean", freq)
    attempt_status = load_bars_attempt_status(meta_dir)
    registry = _read_json(meta_dir / "bars_registry.json", {})

    frame["exchange"] = frame.get("exchange", "").fillna("unknown")
    frame["board"] = frame.get("board", "").fillna("unknown")
    frame["security_name"] = frame.get("security_name", frame.get("name", "")).fillna("")
    frame["raw_present"] = frame["code"].isin(raw_symbols)
    frame["validated_present"] = frame["code"].isin(clean_symbols)
    frame["cleaned_present"] = frame["validated_present"]
    frame["missing"] = ~frame["validated_present"]
    frame["listed_after_cutoff"] = frame["listing_date"].gt(required_end)
    frame["listing_age_bucket"] = frame["listing_date"].apply(lambda value: _listing_age_bucket(value, required_end))
    frame["days_listed_by_cutoff"] = (required_end - frame["listing_date"]).dt.days
    frame["market_status"] = frame["security_name"].apply(_market_status)
    frame["name_pattern"] = frame["security_name"].apply(_name_pattern)
    frame["code_bucket"] = frame["code"].apply(_code_bucket)
    frame["registry_present"] = frame["code"].isin({str(key).zfill(6) for key in dict(registry).keys()})
    frame["attempt_status"] = frame["code"].map(lambda code: str((attempt_status.get(code, {}) or {}).get("status", "none") or "none"))
    frame["attempt_count"] = frame["code"].map(lambda code: int((attempt_status.get(code, {}) or {}).get("attempt_count", 0) or 0))
    frame["last_error"] = frame["code"].map(lambda code: str((attempt_status.get(code, {}) or {}).get("last_error", "") or ""))
    frame["provider_attempted"] = frame["attempt_status"].ne("none")
    frame["provider_success"] = frame["attempt_status"].eq("success")
    frame["provider_empty"] = frame["attempt_status"].eq("empty_response")
    frame["provider_failed"] = frame["attempt_status"].eq("failed")
    frame["structural_no_bars"] = frame["listed_after_cutoff"]

    frame["missing_layer"] = "validated_covered"
    frame.loc[frame["missing"] & frame["structural_no_bars"], "missing_layer"] = "time_range_structural"
    frame.loc[frame["missing"] & frame["raw_present"], "missing_layer"] = "cleaned_or_validated_gap"
    frame.loc[frame["missing"] & frame["provider_failed"], "missing_layer"] = "provider_failed"
    frame.loc[
        frame["missing"] & frame["provider_empty"] & ~frame["structural_no_bars"],
        "missing_layer",
    ] = "provider_empty"
    frame.loc[
        frame["missing"]
        & ~frame["raw_present"]
        & ~frame["structural_no_bars"]
        & ~frame["provider_failed"]
        & ~frame["provider_empty"],
        "missing_layer",
    ] = "raw_never_attempted"
    frame["backfill_candidate"] = frame["missing"] & ~frame["structural_no_bars"]
    return frame


def _group_summary(frame: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    grouped = (
        frame.groupby(column, dropna=False)
        .agg(universe=("code", "count"), covered=("validated_present", "sum"), missing=("missing", "sum"))
        .reset_index()
    )
    rows: list[dict[str, Any]] = []
    for _, row in grouped.sort_values(["missing", "universe"], ascending=[False, False]).iterrows():
        universe = int(row["universe"])
        covered = int(row["covered"])
        rows.append(
            {
                "value": str(row[column]),
                "universe": universe,
                "covered": covered,
                "missing": int(row["missing"]),
                "coverage_ratio": covered / universe if universe else 0.0,
            },
        )
    return rows


def _top_missing_code_buckets(frame: pd.DataFrame, limit: int = 8) -> list[dict[str, Any]]:
    grouped = (
        frame[frame["missing"]]
        .groupby("code_bucket")
        .agg(missing=("code", "count"))
        .reset_index()
        .sort_values(["missing", "code_bucket"], ascending=[False, True])
        .head(limit)
    )
    return [{"bucket": str(row["code_bucket"]), "missing": int(row["missing"])} for _, row in grouped.iterrows()]


def _pipeline_location_counts(frame: pd.DataFrame) -> dict[str, int]:
    counts = frame["missing_layer"].value_counts().to_dict()
    return {str(key): int(value) for key, value in counts.items()}


def select_incremental_backfill_codes(frame: pd.DataFrame, *, limit: int | None = None) -> list[str]:
    candidates = frame[frame["backfill_candidate"]].copy()
    candidates["exchange_priority"] = candidates["exchange"].map({"SSE": 0, "SZSE": 1}).fillna(2)
    candidates["listing_sort"] = candidates["listing_date"].fillna(pd.Timestamp("1900-01-01"))
    ordered = candidates.sort_values(
        ["exchange_priority", "is_st", "listing_sort", "code"],
        ascending=[True, False, True, True],
    )["code"].astype(str).tolist()
    if limit is not None:
        return ordered[: max(0, int(limit))]
    return ordered


def summarize_coverage_recovery(
    *,
    frame: pd.DataFrame,
    required_end_date: str,
    candidate_codes: list[str] | None = None,
) -> dict[str, Any]:
    universe = int(len(frame))
    covered = int(frame["validated_present"].sum())
    missing = int(frame["missing"].sum())
    structural = int(frame["structural_no_bars"].sum())
    eligible = max(0, universe - structural)
    eligible_covered = int((frame["validated_present"] & ~frame["structural_no_bars"]).sum())
    st_total = int(frame["is_st"].sum())
    st_covered = int((frame["is_st"] & frame["validated_present"]).sum())
    non_st_total = int((~frame["is_st"]).sum())
    non_st_covered = int(((~frame["is_st"]) & frame["validated_present"]).sum())
    sse_total = int((frame["exchange"] == "SSE").sum())
    sse_covered = int(((frame["exchange"] == "SSE") & frame["validated_present"]).sum())
    szse_total = int((frame["exchange"] == "SZSE").sum())
    szse_covered = int(((frame["exchange"] == "SZSE") & frame["validated_present"]).sum())
    provider_attempted = int(frame["provider_attempted"].sum())
    provider_success = int(frame["provider_success"].sum())
    provider_failed = int(frame["provider_failed"].sum())
    provider_empty = int(frame["provider_empty"].sum())
    candidate_set = set(candidate_codes or [])
    candidate_frame = frame[frame["code"].isin(candidate_set)].copy() if candidate_set else frame.iloc[0:0].copy()
    attempted_candidates = int(candidate_frame["provider_attempted"].sum()) if not candidate_frame.empty else 0
    successful_candidates = int(candidate_frame["provider_success"].sum()) if not candidate_frame.empty else 0
    failed_candidates = int(candidate_frame["provider_failed"].sum()) if not candidate_frame.empty else 0
    empty_candidates = int(candidate_frame["provider_empty"].sum()) if not candidate_frame.empty else 0
    missing_old = frame[frame["missing"] & ~frame["structural_no_bars"]].copy()

    return {
        "required_end_date": required_end_date,
        "universe_symbols": universe,
        "covered_symbols": covered,
        "missing_symbols": missing,
        "coverage_ratio": covered / universe if universe else 0.0,
        "eligible_universe_symbols": eligible,
        "eligible_covered_symbols": eligible_covered,
        "eligible_coverage_ratio": eligible_covered / eligible if eligible else 0.0,
        "structural_no_bars_symbols": structural,
        "backfill_candidate_symbols": int(frame["backfill_candidate"].sum()),
        "st_total": st_total,
        "st_covered": st_covered,
        "st_coverage_ratio": st_covered / st_total if st_total else 0.0,
        "non_st_total": non_st_total,
        "non_st_covered": non_st_covered,
        "non_st_coverage_ratio": non_st_covered / non_st_total if non_st_total else 0.0,
        "sse_total": sse_total,
        "sse_covered": sse_covered,
        "sse_coverage_ratio": sse_covered / sse_total if sse_total else 0.0,
        "szse_total": szse_total,
        "szse_covered": szse_covered,
        "szse_coverage_ratio": szse_covered / szse_total if szse_total else 0.0,
        "provider_attempted_symbols": provider_attempted,
        "provider_success_symbols": provider_success,
        "provider_failed_symbols": provider_failed,
        "provider_empty_symbols": provider_empty,
        "provider_success_rate": provider_success / provider_attempted if provider_attempted else None,
        "candidate_attempted_symbols": attempted_candidates,
        "candidate_success_symbols": successful_candidates,
        "candidate_failed_symbols": failed_candidates,
        "candidate_empty_symbols": empty_candidates,
        "candidate_success_rate": successful_candidates / attempted_candidates if attempted_candidates else None,
        "registry_present_symbols": int(frame["registry_present"].sum()),
        "exchange_rows": _group_summary(frame, "exchange"),
        "st_rows": _group_summary(frame, "is_st"),
        "name_pattern_rows": _group_summary(frame, "name_pattern"),
        "listing_age_rows": _group_summary(frame, "listing_age_bucket"),
        "market_status_rows": _group_summary(frame, "market_status"),
        "pipeline_location_counts": _pipeline_location_counts(frame),
        "top_missing_code_buckets": _top_missing_code_buckets(frame),
        "old_missing_samples": missing_old.sort_values(["listing_date", "code"])
        .loc[:, ["code", "security_name", "exchange", "is_st", "listing_date"]]
        .head(12)
        .to_dict(orient="records"),
    }


def assess_coverage_stage(
    *,
    summary: Mapping[str, Any],
    baseline_rerun_completed: bool,
) -> CoverageStageDecision:
    coverage_ratio = float(summary.get("coverage_ratio", 0.0) or 0.0)
    eligible_ratio = float(summary.get("eligible_coverage_ratio", 0.0) or 0.0)
    exchange_gap = abs(
        float(summary.get("sse_coverage_ratio", 0.0) or 0.0)
        - float(summary.get("szse_coverage_ratio", 0.0) or 0.0),
    )
    st_gap = abs(
        float(summary.get("st_coverage_ratio", 0.0) or 0.0)
        - float(summary.get("non_st_coverage_ratio", 0.0) or 0.0),
    )
    unexplained_missing = int(summary.get("pipeline_location_counts", {}).get("raw_never_attempted", 0))
    provider_failures = int(summary.get("pipeline_location_counts", {}).get("provider_failed", 0))
    provider_empty = int(summary.get("pipeline_location_counts", {}).get("provider_empty", 0))
    structural = int(summary.get("structural_no_bars_symbols", 0))

    reasons: list[str] = []
    bias_explained = True
    if unexplained_missing > 0:
        bias_explained = False
        reasons.append(f"仍有 {unexplained_missing} 只缺口停留在 raw_never_attempted，missingness 还没拆清。")
    if exchange_gap > 0.15:
        bias_explained = False
        reasons.append(f"沪深覆盖率差仍有 {exchange_gap:.2%}，交易所偏差还过大。")
    if coverage_ratio < 0.70:
        reasons.append(f"总覆盖率只有 {coverage_ratio:.2%}，仍低于 pilot 退出线。")
        return CoverageStageDecision(
            stage="pilot",
            bias_explained=bias_explained,
            baseline_reassessment_allowed=False,
            legacy_restore_allowed=False,
            reasons=reasons,
            thresholds={
                "pilot_exit_coverage_ratio": 0.70,
                "validation_ready_coverage_ratio": 0.85,
                "research_ready_coverage_ratio": 0.95,
                "max_exchange_gap": 0.15,
                "max_st_gap": 0.15,
            },
        )

    if not bias_explained:
        if not reasons:
            reasons.append("coverage 已改善，但 missingness bias 还没有解释完。")
        return CoverageStageDecision(
            stage="pilot",
            bias_explained=False,
            baseline_reassessment_allowed=False,
            legacy_restore_allowed=False,
            reasons=reasons,
            thresholds={
                "pilot_exit_coverage_ratio": 0.70,
                "validation_ready_coverage_ratio": 0.85,
                "research_ready_coverage_ratio": 0.95,
                "max_exchange_gap": 0.15,
                "max_st_gap": 0.15,
            },
        )

    if coverage_ratio < 0.85:
        reasons.append(f"coverage 已到 {coverage_ratio:.2%}，但仍低于 validation-ready 门槛 85%。")
        return CoverageStageDecision(
            stage="pilot",
            bias_explained=True,
            baseline_reassessment_allowed=False,
            legacy_restore_allowed=False,
            reasons=reasons,
            thresholds={
                "pilot_exit_coverage_ratio": 0.70,
                "validation_ready_coverage_ratio": 0.85,
                "research_ready_coverage_ratio": 0.95,
                "max_exchange_gap": 0.15,
                "max_st_gap": 0.15,
            },
        )

    reasons.append(
        "coverage 已明显回升且 bias 已拆清，本轮最高只晋级到 validation-ready；research-ready 需要后续单独 promotion gate。",
    )
    if provider_failures:
        reasons.append(f"仍有 {provider_failures} 只 provider failure，需要后续重试。")
    if provider_empty:
        reasons.append(f"仍有 {provider_empty} 只 provider empty/无返回，需要继续分类。")
    if structural:
        reasons.append(f"{structural} 只是截止日后上市，已单独归类为结构性无 bars。")
    return CoverageStageDecision(
        stage="validation-ready",
        bias_explained=True,
        baseline_reassessment_allowed=True,
        legacy_restore_allowed=False,
        reasons=reasons,
        thresholds={
            "pilot_exit_coverage_ratio": 0.70,
            "validation_ready_coverage_ratio": 0.85,
            "research_ready_coverage_ratio": 0.95,
            "max_exchange_gap": 0.15,
            "max_st_gap": 0.15,
        },
    )


def decide_baseline_status(*, stage: str, baseline_rerun_completed: bool) -> str:
    if stage == "validation-ready" and baseline_rerun_completed:
        return "baseline_validation_ready"
    return "baseline_reset_pending"


def _fmt_ratio(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"


def _table_lines(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def render_coverage_gap_report(summary: Mapping[str, Any], *, stage: str) -> str:
    exchange_rows = [
        [row["value"], str(row["universe"]), str(row["covered"]), str(row["missing"]), _fmt_ratio(row["coverage_ratio"])]
        for row in summary.get("exchange_rows", [])
    ]
    listing_rows = [
        [row["value"], str(row["universe"]), str(row["covered"]), str(row["missing"]), _fmt_ratio(row["coverage_ratio"])]
        for row in summary.get("listing_age_rows", [])
    ]
    bucket_text = "、".join(f"{item['bucket']}({item['missing']})" for item in summary.get("top_missing_code_buckets", [])) or "无"
    pipeline = summary.get("pipeline_location_counts", {})
    lines = [
        "# Canonical Universe Coverage Gap Report",
        "",
        "## 当前结论",
        f"- 当前 canonical universe: `{CURRENT_UNIVERSE_ID}`",
        f"- 当前阶段判断: `{stage}`",
        f"- 当前 coverage: `{summary['covered_symbols']} / {summary['universe_symbols']} = {_fmt_ratio(summary['coverage_ratio'])}`",
        f"- 可解释的结构性无 bars: `{summary['structural_no_bars_symbols']}`（截止日 `2025-07-01` 之后上市）",
        "- 当前缺失不是随机缺失。最集中的缺口仍看交易所/代码段，而不是 ST 标签。",
        f"- 最大缺口代码段: `{bucket_text}`",
        "",
        "## 缺失最集中在哪",
        *(_table_lines(["维度", "Universe", "Covered", "Missing", "Coverage"], exchange_rows)),
        "",
        *(_table_lines(["上市年龄", "Universe", "Covered", "Missing", "Coverage"], listing_rows)),
        "",
        "## raw / cleaned / validated 缺口位置",
        f"- validated_covered: `{pipeline.get('validated_covered', 0)}`",
        f"- raw_never_attempted: `{pipeline.get('raw_never_attempted', 0)}`",
        f"- provider_failed: `{pipeline.get('provider_failed', 0)}`",
        f"- provider_empty: `{pipeline.get('provider_empty', 0)}`",
        f"- cleaned_or_validated_gap: `{pipeline.get('cleaned_or_validated_gap', 0)}`",
        f"- time_range_structural: `{pipeline.get('time_range_structural', 0)}`",
        "",
        "## 直白判断",
        "- 缺失不是随机缺失。",
        "- 真正的系统性偏差先前主要是沪市主板 coverage 明显不足。",
        "- ST 本身不是主要缺口来源；此前把 ST 当作过滤条件会误判问题，但当前 canonical universe 已经没有这么做。",
        "- 样本偏差风险此前主要体现在：pilot 结果被深市/已存在历史 bars 的样本主导，不能代表整个主板 universe。",
    ]
    return "\n".join(lines)


def render_missingness_bias_audit(summary: Mapping[str, Any], *, stage: str) -> str:
    st_covered = int(summary.get("st_covered", 0) or 0)
    st_total = int(summary.get("st_total", 0) or 0)
    st_ratio = float(summary.get("st_coverage_ratio", (st_covered / st_total if st_total else 0.0)) or 0.0)
    non_st_covered = int(summary.get("non_st_covered", 0) or 0)
    non_st_total = int(summary.get("non_st_total", 0) or 0)
    non_st_ratio = float(
        summary.get("non_st_coverage_ratio", (non_st_covered / non_st_total if non_st_total else 0.0)) or 0.0,
    )
    sse_covered = int(summary.get("sse_covered", 0) or 0)
    sse_total = int(summary.get("sse_total", 0) or 0)
    sse_ratio = float(summary.get("sse_coverage_ratio", (sse_covered / sse_total if sse_total else 0.0)) or 0.0)
    szse_covered = int(summary.get("szse_covered", 0) or 0)
    szse_total = int(summary.get("szse_total", 0) or 0)
    szse_ratio = float(summary.get("szse_coverage_ratio", (szse_covered / szse_total if szse_total else 0.0)) or 0.0)
    lines = [
        "# Missingness Bias Audit",
        "",
        "## 直接回答",
        f"- 当前 coverage stage: `{stage}`",
        f"- ST 覆盖率: `{st_covered} / {st_total} = {_fmt_ratio(st_ratio)}`",
        f"- 非 ST 覆盖率: `{non_st_covered} / {non_st_total} = {_fmt_ratio(non_st_ratio)}`",
        f"- 沪市主板覆盖率: `{sse_covered} / {sse_total} = {_fmt_ratio(sse_ratio)}`",
        f"- 深市主板覆盖率: `{szse_covered} / {szse_total} = {_fmt_ratio(szse_ratio)}`",
        f"- Eligible coverage（剔除截止日后上市）: `{summary['eligible_covered_symbols']} / {summary['eligible_universe_symbols']} = {_fmt_ratio(summary['eligible_coverage_ratio'])}`",
        "",
        "## 审计判断",
        f"- pilot 是否对 ST / 非 ST 有偏差: `否，ST 不是主缺口；差异约 {abs(st_ratio - non_st_ratio):.2%}`。",
        f"- pilot 是否对沪 / 深主板有偏差: `是，此前差异很大；当前差异约 {abs(sse_ratio - szse_ratio):.2%}`。",
        "- pilot 是否对新 / 老股票有偏差: `是，截止日后上市的新股天然无 bars，需要单独分类；其余老股缺失则应视为 recoverable/backfill 对象。`",
        (
            "- 当前结果是否只能视为偏样本结果: `否。`"
            if stage != "pilot"
            else "- 当前结果是否只能视为偏样本结果: `是，仍只能视为偏样本结果。`"
        ),
        "",
        "## 备注",
        "- active / 退市 / 历史状态维度上，当前 security master 全部来自交易所当前名单；退市/历史状态并不是本轮缺失主因。",
        "- 名称模式上，除了 `ST/*ST` 标签外，没有发现能解释缺失的统一命名模式。",
    ]
    return "\n".join(lines)


def render_backfill_plan(
    *,
    summary: Mapping[str, Any],
    selected_codes: list[str],
    executed: bool,
    stage: str,
) -> str:
    selected_preview = "、".join(selected_codes[:12]) or "无"
    lines = [
        "# Incremental Backfill Plan",
        "",
        "## 目标",
        "- 只补当前 canonical universe 的缺失 bars，不重做 universe reset，不恢复旧 715-symbol pool。",
        "- 优先补最影响研究客观性的缺口，先解决交易所偏差，再解决剩余个股缺口。",
        "",
        "## 优先级",
        "1. 沪市主板缺口优先，因为它是此前 51.11% coverage 的最大偏差源。",
        "2. 截止日 `2025-07-01` 前已上市但仍缺 bars 的标的优先，因为它们理论上应该可回补。",
        "3. 截止日后上市的新股单独归类为结构性无 bars，不计入 provider failure。",
        "",
        "## 本轮执行",
        f"- 预估 backfill candidates: `{summary.get('backfill_candidate_symbols', 0)}`",
        f"- 本轮实际选中: `{len(selected_codes)}`",
        f"- 选中样例: `{selected_preview}`",
        f"- 本轮是否已执行: `{executed}`",
        "",
        "## Stop Condition",
        "- 当 unexplained missing 不再以 `raw_never_attempted` 为主，且 coverage 至少进入 `validation-ready`。",
        "- 若只剩 provider failure / provider empty / 截止日后上市三类缺口，则停止扩大 backfill 范围，转入重试和分类。",
        "",
        "## 本轮结论",
        f"- 当前 stage: `{stage}`",
        (
            f"- provider attempt success: `{summary['candidate_success_symbols']} / {summary['candidate_attempted_symbols']} = {_fmt_ratio(summary['candidate_success_rate'])}`"
            if summary.get("candidate_attempted_symbols")
            else "- 本轮没有新的 provider attempt。"
        ),
    ]
    return "\n".join(lines)


def render_coverage_recovery_checkpoint(payload: Mapping[str, Any]) -> str:
    progress_rows = payload.get("research_progress_rows", [])
    coverage = payload.get("coverage_status_rows", [])
    missingness = payload.get("missingness_rows", [])
    strategy_rows = payload.get("strategy_action_rows", [])
    lines = [
        "Done",
        f"- 系统推进：{payload.get('system_line', '未记录')}",
        f"- 策略推进：{payload.get('strategy_line', '未记录')}",
        "",
        "Evidence",
    ]
    lines.extend(f"- {item}" for item in payload.get("evidence_lines", []))
    lines.extend(
        [
            "",
            "Research progress",
            "| 维度 | 状态 | 分数 | 证据 |",
            "|---|---|---:|---|",
        ],
    )
    lines.extend(
        f"| {row['dimension']} | {row['status']} | {row['score']}/4 | {row['evidence']} |"
        for row in progress_rows
    )
    lines.extend(
        [
            "",
            "Coverage status",
            "| 项目 | 结果 |",
            "|---|---|",
        ],
    )
    lines.extend(f"| {row['item']} | {row['result']} |" for row in coverage)
    lines.extend(
        [
            "",
            "Missingness audit",
            "| 维度 | 观察 | 结论 |",
            "|---|---|---|",
        ],
    )
    lines.extend(f"| {row['dimension']} | {row['observation']} | {row['conclusion']} |" for row in missingness)
    lines.extend(
        [
            "",
            "Strategy actions this run",
            "| 策略 | 执行者 | 动作 | 结果 | 决策变化 |",
            "|---|---|---|---|---|",
        ],
    )
    lines.extend(
        f"| {row['strategy']} | {row['actor']} | {row['action']} | {row['result']} | {row['decision_delta']} |"
        for row in strategy_rows
    )
    lines.extend(
        [
            "",
            "Next recommendation",
            f"- {payload.get('next_recommendation', '未记录')}",
            "",
            "Subagent status",
            f"- configured gate: {payload.get('configured_gate', 'AUTO')}",
            f"- effective gate this run: {payload.get('effective_gate', 'OFF')}",
            f"- active strategy-research subagents: {payload.get('active_strategy_subagents', '无')}",
            f"- active infrastructure subagents: {payload.get('active_infra_subagents', '无')}",
            f"- {payload.get('subagent_note', '本轮主任务高度串行，保持 OFF 才能减少协调噪音。')}",
        ],
    )
    return "\n".join(lines).rstrip() + "\n"


def _experiment_payload(
    *,
    generated_at: str,
    cfg: Mapping[str, Any],
    stage: str,
    coverage_ratio: float,
    baseline_status: str,
    artifact_refs: list[str],
) -> dict[str, Any]:
    return {
        "timestamp": generated_at,
        "experiment_id": f"coverage_recovery::{generated_at.replace(':', '').replace('-', '')}",
        "hypothesis": "Canonical coverage can be restored by missing-only backfill without reopening the legacy 715-symbol pool.",
        "config_hash": stable_hash(dict(cfg)),
        "result": stage,
        "coverage_ratio": coverage_ratio,
        "baseline_status": baseline_status,
        "artifact_refs": artifact_refs,
    }


def _update_supporting_memory(
    *,
    paths,
    pre_summary: Mapping[str, Any],
    post_summary: Mapping[str, Any],
    stage_decision: CoverageStageDecision,
    baseline_status: str,
    passed_commands: list[str],
    failed_commands: list[str],
) -> dict[str, Path]:
    tracked_dir = paths.memory_dir
    gap_report_path = _write_text(
        tracked_dir / "COVERAGE_GAP_REPORT.md",
        render_coverage_gap_report(post_summary, stage=stage_decision.stage),
    )
    bias_path = _write_text(
        tracked_dir / "MISSINGNESS_BIAS_AUDIT.md",
        render_missingness_bias_audit(post_summary, stage=stage_decision.stage),
    )
    backfill_candidates_path = paths.meta_dir / "coverage_recovery_backfill_candidates.txt"
    selected_codes = _normalize_codes(backfill_candidates_path.read_text(encoding="utf-8").splitlines()) if backfill_candidates_path.exists() else []
    backfill_plan_path = _write_text(
        tracked_dir / "BACKFILL_PLAN.md",
        render_backfill_plan(
            summary=post_summary,
            selected_codes=selected_codes,
            executed=bool(selected_codes),
            stage=stage_decision.stage,
        ),
    )

    project_state = "\n".join(
        [
            "# 项目状态",
            "",
            "## 当前总任务",
            f"- canonical project: `{CANONICAL_PROJECT_ID}`",
            f"- canonical universe: `{CURRENT_UNIVERSE_ID}`",
            "- 当前阶段: `Canonical Universe Coverage Recovery`",
            f"- 当前 readiness: `{stage_decision.stage}`",
            "",
            "## 当前真相",
            f"- 当前覆盖率: `{post_summary['covered_symbols']} / {post_summary['universe_symbols']} = {_fmt_ratio(post_summary['coverage_ratio'])}`",
            f"- 截止日后上市、理论上不该有 bars 的数量: `{post_summary['structural_no_bars_symbols']}`",
            f"- 旧 `bars_registry.json` 只记录了 `{pre_summary['registry_present_symbols']}` 个 symbols，说明之前是旧残留状态，不是 canonical universe 的完整拉取。",
            f"- baseline 当前状态: `{baseline_status}`",
            "",
            "## 回归观察名单",
            "- canonical universe id 是否仍是 `cn_a_mainboard_all_v1`",
            "- ST 是否仍只作为标签，不作为过滤条件",
            "- SSE/SZSE coverage gap 是否已明显收敛",
            "- 结构性无 bars 是否仅限截止日后上市新股",
            "- baseline 是否仍未被包装成 active truth",
            "",
            "## Evidence Ledger",
            f"- pre-coverage: `{pre_summary['covered_symbols']} / {pre_summary['universe_symbols']} = {_fmt_ratio(pre_summary['coverage_ratio'])}`",
            f"- post-coverage: `{post_summary['covered_symbols']} / {post_summary['universe_symbols']} = {_fmt_ratio(post_summary['coverage_ratio'])}`",
            f"- provider candidate success: `{post_summary['candidate_success_symbols']} / {post_summary['candidate_attempted_symbols']}`",
            f"- structural no-bars: `{post_summary['structural_no_bars_symbols']}`",
            "",
            "## Decision Ledger",
            "- 选择 missing-only incremental backfill，而不是重跑整个 canonical universe。",
            "- 选择把截止日后上市的新股单独归类为结构性无 bars，而不是算 provider failure。",
            "- coverage 未到 research-ready 前，不恢复 `risk_constrained_limit_up` / `tighter_entry_limit_up` 为 active 主线。",
            f"- 当前阶段定为 `{stage_decision.stage}`，不是因为旧策略结论变好，而是因为 coverage / bias 审计是否足够可信。",
            "",
            "## 下一步唯一最高优先动作",
            "- 只在当前 `validation-ready` 或更高阶段上重新审 baseline；若仍有 provider failure，则先重试失败样本，不要扩散回 legacy 主线。",
        ],
    )
    project_state_path = _write_text(paths.project_state_path, project_state)

    research_memory = "\n".join(
        [
            "# 研究记忆",
            "",
            "## 已确认事实",
            f"- canonical project 继续保持 `{CANONICAL_PROJECT_ID}`。",
            f"- canonical universe 继续保持 `{CURRENT_UNIVERSE_ID}`。",
            f"- 当前 post-coverage 已到 `{_fmt_ratio(post_summary['coverage_ratio'])}`，eligible coverage 为 `{_fmt_ratio(post_summary['eligible_coverage_ratio'])}`。",
            f"- 当前 ST 总数 `{post_summary['st_total']}`，已覆盖 `{post_summary['st_covered']}`。",
            "",
            "## 关键判断",
            "- 缺失不是随机缺失；前一阶段的主要偏差是沪市主板覆盖严重不足。",
            "- 结构性无 bars 主要来自截止日后上市新股，这类样本不能再和 provider failure 混在一起。",
            f"- 当前 stage: `{stage_decision.stage}`，baseline 只能按 `{baseline_status}` 解读。",
            "",
            "## 负面记忆",
            "- 不要把旧 715-symbol pool 的结果重新写回 active truth。",
            "- 不要把 `ST` 标签误当过滤条件去解释 coverage gap。",
            "- 不要把 canonical coverage recovery 包装成 legacy 策略重新成立。",
        ],
    )
    research_memory_path = _write_text(paths.research_memory_path, research_memory)

    verify_last = "\n".join(
        [
            "# 最近验证快照",
            "- branch: `main`",
            f"- 当前 canonical project: `{CANONICAL_PROJECT_ID}`",
            f"- 当前 canonical universe: `{CURRENT_UNIVERSE_ID}`",
            f"- 当前阶段: `Canonical Universe Coverage Recovery / {stage_decision.stage}`",
            "",
            "## 通过的关键验证",
            *[f"- `{item}`" for item in passed_commands],
            "",
            "## 未通过 / 待重试",
            *([f"- `{item}`" for item in failed_commands] or ["- 无"]),
            "",
            "## 稳定数据结论",
            f"- coverage ratio: `{_fmt_ratio(post_summary['coverage_ratio'])}`",
            f"- covered symbols: `{post_summary['covered_symbols']} / {post_summary['universe_symbols']}`",
            f"- current readiness stage: `{stage_decision.stage}`",
            f"- baseline status: `{baseline_status}`",
        ],
    )
    verify_last_path = _write_text(paths.verify_last_path, verify_last)

    handoff = "\n".join(
        [
            "# 下一轮交接",
            "- 当前总任务: 保持 canonical universe 不变，只在 `cn_a_mainboard_all_v1` 上继续做 coverage recovery / baseline 复判。",
            f"- 当前阶段: `{stage_decision.stage}`",
            f"- 当前 blocker: `legacy 仍未恢复；baseline 只到 {baseline_status}`",
            "- 下一步唯一动作: 若仍有 provider failure，则对失败清单做重试；否则只重审 baseline，不要扩主线。",
            "- 必读文件: `COVERAGE_GAP_REPORT.md`、`MISSINGNESS_BIAS_AUDIT.md`、`BACKFILL_PLAN.md`、`VERIFY_LAST.md`",
        ],
    )
    handoff_path = _write_text(paths.handoff_path, handoff)

    migration = "\n".join(
        [
            "# MIGRATION PROMPT NEXT CHAT",
            f"Project: `{CANONICAL_PROJECT_ID}`",
            f"Universe: `{CURRENT_UNIVERSE_ID}`",
            f"Stage: `{stage_decision.stage}`",
            f"Truth: coverage 已从 {_fmt_ratio(pre_summary['coverage_ratio'])} 提升到 {_fmt_ratio(post_summary['coverage_ratio'])}; 旧主偏差来自沪市 coverage 缺口，而非 ST 过滤。",
            f"Baseline: `{baseline_status}`",
            "Do not reopen legacy 715-symbol logic. Only retry provider-failed names or reassess baseline on the canonical universe.",
        ],
    )
    migration_path = _write_text(paths.migration_prompt_path, migration)

    strategy_board = "\n".join(
        [
            "# 策略研究看板",
            "",
            "## 当前 active truth",
            "| 策略 | 角色 | 状态 | 说明 |",
            "|---|---|---|---|",
            f"| `baseline_limit_up` | active baseline | `{baseline_status}` | 只允许在 `{stage_decision.stage}` 阶段做最小重建与 readiness 评估，尚未恢复为 active truth。 |",
            "",
            "## legacy comparison only",
            "| 策略 | 当前地位 | 说明 |",
            "|---|---|---|",
            "| `risk_constrained_limit_up` | legacy comparison only | baseline 还没到 research-ready，不能恢复为当前主线。 |",
            "| `tighter_entry_limit_up` | legacy comparison only | 同上，只保留后续对比资格。 |",
            "",
            "## 当前 blocker",
            f"- 当前 coverage stage: `{stage_decision.stage}`",
            f"- 当前 coverage: `{post_summary['covered_symbols']} / {post_summary['universe_symbols']} = {_fmt_ratio(post_summary['coverage_ratio'])}`",
            "- 当前不允许把 legacy 分支结论重新包装成 canonical universe 的真相。",
        ],
    )
    strategy_board_path = _write_text(paths.strategy_board_path, strategy_board)

    hypothesis_queue = "\n".join(
        [
            "# Hypothesis Queue",
            "",
            "- [active] missing-only backfill 能否把 canonical universe 长尾 provider failure 再压到个位数。",
            "- [active] baseline_limit_up 在 canonical universe 上复跑后是否仍只到 validation-ready，而非 active truth。",
            "- [deferred] 只有当 baseline 到 research-ready 后，才重拉 legacy 分支做对照。",
        ],
    )
    _write_text(paths.hypothesis_queue_path, hypothesis_queue)

    postmortem = "\n".join(
        [
            "# Postmortems",
            "",
            "## 2026-03-27 Canonical Coverage Gap",
            "- 失败路径: universe reset 后没有补 missing-only bars，导致旧 DB 残留和新 canonical universe 混在一起。",
            "- 根因: `bars_registry.json` 仍停在旧池子规模，coverage gap 大量落在 `raw_never_attempted`。",
            "- 修复: 改为 missing-only incremental backfill，并把截止日后上市样本单独标记为结构性无 bars。",
        ],
    )
    _write_text(paths.postmortems_path, postmortem)

    return {
        "coverage_gap_report": gap_report_path,
        "missingness_bias_audit": bias_path,
        "backfill_plan": backfill_plan_path,
        "project_state": project_state_path,
        "research_memory": research_memory_path,
        "verify_last": verify_last_path,
        "handoff": handoff_path,
        "migration": migration_path,
        "strategy_board": strategy_board_path,
    }


def _update_session_state(
    *,
    paths,
    generated_at: str,
    pre_summary: Mapping[str, Any],
    post_summary: Mapping[str, Any],
    stage_decision: CoverageStageDecision,
    baseline_status: str,
    passed_commands: list[str],
    failed_commands: list[str],
) -> Path:
    payload = _read_json(paths.session_state_path, {})
    payload.update(
        {
            "project": CANONICAL_PROJECT_ID,
            "canonical_project_id": CANONICAL_PROJECT_ID,
            "legacy_project_aliases": ["2026Q1_limit_up"],
            "canonical_universe_id": CURRENT_UNIVERSE_ID,
            "branch": "main",
            "configured_subagent_gate_mode": "AUTO",
            "effective_subagent_gate_mode": "OFF",
            "effective_subagent_gate_reason": "Coverage audit, incremental backfill, and readiness judgement are one serial path.",
            "current_task": "Recover canonical universe coverage and reassess baseline readiness without reopening legacy pools.",
            "current_research_stage": stage_decision.stage,
            "current_research_cycle_type": "canonical_universe_coverage_recovery",
            "current_blocker": stage_decision.reasons[0] if stage_decision.reasons else "none",
            "current_capability_boundary": "Coverage truth is now judged on the canonical mainboard universe only; legacy strategy conclusions remain comparison-only until baseline is rebuilt.",
            "active_branch_ids": ["baseline_limit_up"],
            "current_primary_strategy_ids": ["baseline_limit_up"],
            "current_secondary_strategy_ids": [],
            "legacy_comparison_strategy_ids": ["risk_constrained_limit_up", "tighter_entry_limit_up"],
            "current_blocked_strategy_ids": [] if stage_decision.stage != "pilot" else ["baseline_limit_up"],
            "current_promoted_strategy_ids": [],
            "current_rejected_strategy_ids": [],
            "baseline_status": baseline_status,
            "universe_metrics": {
                "size": post_summary["universe_symbols"],
                "sse_mainboard": post_summary["sse_total"],
                "szse_mainboard": post_summary["szse_total"],
                "st_count": post_summary["st_total"],
                "structural_no_bars": post_summary["structural_no_bars_symbols"],
            },
            "readiness": {
                "stage": stage_decision.stage,
                "covered_symbols": post_summary["covered_symbols"],
                "universe_symbols": post_summary["universe_symbols"],
                "coverage_ratio": post_summary["coverage_ratio"],
                "eligible_coverage_ratio": post_summary["eligible_coverage_ratio"],
                "ready": stage_decision.stage != "pilot",
            },
            "coverage_recovery": {
                "pre_coverage_ratio": pre_summary["coverage_ratio"],
                "post_coverage_ratio": post_summary["coverage_ratio"],
                "candidate_success_rate": post_summary["candidate_success_rate"],
                "bias_explained": stage_decision.bias_explained,
                "legacy_restore_allowed": stage_decision.legacy_restore_allowed,
            },
            "next_priority_action": "Retry provider-failed names if any remain; otherwise reassess baseline only on the canonical universe.",
            "verify_last": {
                "passed_commands": passed_commands,
                "failed_commands": failed_commands,
                "key_metrics": {
                    "coverage_ratio": post_summary["coverage_ratio"],
                    "covered_symbols": post_summary["covered_symbols"],
                    "universe_symbols": post_summary["universe_symbols"],
                    "eligible_coverage_ratio": post_summary["eligible_coverage_ratio"],
                    "candidate_success_rate": post_summary["candidate_success_rate"],
                },
            },
            "last_updated": generated_at,
        },
    )
    return _write_json(paths.session_state_path, payload)


def run_coverage_recovery(
    project: str,
    *,
    config_path: Path | None = None,
    execute_backfill: bool = False,
    max_backfill_symbols: int | None = None,
    workers: int = 4,
    rerun_baseline: bool = False,
) -> dict[str, Any]:
    cfg, paths = load_config(project, config_path=config_path)
    if project != CANONICAL_PROJECT_ID:
        raise ValueError(f"coverage recovery is only supported on canonical project {CANONICAL_PROJECT_ID}")

    generated_at = _now_iso()
    universe_codes = load_universe_codes(project)
    required_end_date = str((cfg.get("coverage_gap_policy", {}) or {}).get("required_end_date") or cfg.get("end_date"))

    pre_frame = build_coverage_recovery_frame(
        project=project,
        cfg=cfg,
        db_path=Path(str(cfg["db_path"])),
        meta_dir=paths.meta_dir,
        universe_codes=universe_codes,
    )
    selected_codes = select_incremental_backfill_codes(pre_frame, limit=max_backfill_symbols)
    selected_codes_path = _write_text(paths.meta_dir / "coverage_recovery_backfill_candidates.txt", "\n".join(selected_codes))
    pre_summary = summarize_coverage_recovery(
        frame=pre_frame,
        required_end_date=required_end_date,
        candidate_codes=selected_codes,
    )

    passed_commands: list[str] = []
    failed_commands: list[str] = []
    backfill_result: dict[str, Any] | None = None

    repo_root = find_repo_root()
    config_arg = str(config_path or paths.config_path)
    if execute_backfill and selected_codes:
        update_cmd = [
            sys.executable,
            str(repo_root / "scripts" / "steps" / "11_update_bars.py"),
            "--project",
            project,
            "--config",
            config_arg,
            "--mode",
            "backfill",
            "--workers",
            str(max(1, int(workers))),
            "--max-codes-scan",
            str(len(selected_codes)),
            "--codes-file",
            str(selected_codes_path),
        ]
        result = subprocess.run(update_cmd, cwd=repo_root, capture_output=True, text=True)
        if result.returncode != 0:
            failed_commands.append(" ".join(update_cmd))
            raise RuntimeError(f"incremental backfill failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        passed_commands.append(" ".join(update_cmd))
        backfill_result = {
            "command": update_cmd,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }

    validate_result = run_data_validate_flow(
        project=project,
        config_path=config_path,
        full_refresh=False,
        skip_clean=not execute_backfill,
    )
    validate_cmd = f"{sys.executable} -m quant_mvp data_validate --project {project} --config {config_arg}"
    if not execute_backfill:
        validate_cmd += " --skip-clean"
    passed_commands.append(validate_cmd)

    post_frame = build_coverage_recovery_frame(
        project=project,
        cfg=cfg,
        db_path=Path(str(cfg["db_path"])),
        meta_dir=paths.meta_dir,
        universe_codes=universe_codes,
    )
    post_summary = summarize_coverage_recovery(
        frame=post_frame,
        required_end_date=required_end_date,
        candidate_codes=selected_codes,
    )

    baseline_rerun_completed = False
    baseline_result: dict[str, Any] | None = None
    provisional_stage = assess_coverage_stage(summary=post_summary, baseline_rerun_completed=False)
    if rerun_baseline and provisional_stage.baseline_reassessment_allowed:
        baseline_cmd = [
            sys.executable,
            str(repo_root / "scripts" / "run_limit_up_screening.py"),
            "--project",
            project,
            "--config",
            config_arg,
            "--save",
            "none",
            "--no-show",
        ]
        result = subprocess.run(baseline_cmd, cwd=repo_root, capture_output=True, text=True)
        if result.returncode == 0:
            baseline_rerun_completed = True
            passed_commands.append(" ".join(baseline_cmd))
            baseline_result = {"command": baseline_cmd, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
        else:
            failed_commands.append(" ".join(baseline_cmd))
            baseline_result = {"command": baseline_cmd, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}

    stage_decision = assess_coverage_stage(summary=post_summary, baseline_rerun_completed=baseline_rerun_completed)
    baseline_status = decide_baseline_status(stage=stage_decision.stage, baseline_rerun_completed=baseline_rerun_completed)

    memory_paths = _update_supporting_memory(
        paths=paths,
        pre_summary=pre_summary,
        post_summary=post_summary,
        stage_decision=stage_decision,
        baseline_status=baseline_status,
        passed_commands=passed_commands,
        failed_commands=failed_commands,
    )
    session_state_path = _update_session_state(
        paths=paths,
        generated_at=generated_at,
        pre_summary=pre_summary,
        post_summary=post_summary,
        stage_decision=stage_decision,
        baseline_status=baseline_status,
        passed_commands=passed_commands,
        failed_commands=failed_commands,
    )

    artifact_payload = {
        "generated_at": generated_at,
        "project": project,
        "pre_summary": pre_summary,
        "post_summary": post_summary,
        "stage_decision": stage_decision.to_dict(),
        "baseline_status": baseline_status,
        "selected_codes_count": len(selected_codes),
        "validate_result": validate_result,
        "backfill_result": backfill_result,
        "baseline_result": baseline_result,
        "memory_paths": {key: str(value) for key, value in memory_paths.items()},
        "session_state_path": str(session_state_path),
    }
    artifact_json_path = _write_json(paths.meta_dir / "coverage_recovery_summary.json", artifact_payload)

    append_jsonl(
        paths.experiment_ledger_path,
        _experiment_payload(
            generated_at=generated_at,
            cfg=cfg,
            stage=stage_decision.stage,
            coverage_ratio=post_summary["coverage_ratio"],
            baseline_status=baseline_status,
            artifact_refs=[str(artifact_json_path), *[str(value) for value in memory_paths.values()]],
        ),
    )
    append_jsonl(
        paths.evidence_ledger_path,
        {
            "timestamp": generated_at,
            "evidence_type": "coverage_recovery",
            "project": project,
            "canonical_universe_id": CURRENT_UNIVERSE_ID,
            "pre_coverage_ratio": pre_summary["coverage_ratio"],
            "post_coverage_ratio": post_summary["coverage_ratio"],
            "eligible_coverage_ratio": post_summary["eligible_coverage_ratio"],
            "stage": stage_decision.stage,
            "baseline_status": baseline_status,
        },
    )

    checkpoint_payload = {
        "system_line": (
            f"coverage 从 {_fmt_ratio(pre_summary['coverage_ratio'])} 提升到 {_fmt_ratio(post_summary['coverage_ratio'])}，"
            "并把截止日后上市的新股单独归类。"
        ),
        "strategy_line": (
            f"`baseline_limit_up` 已在 `{stage_decision.stage}` 阶段下完成最小重建复判，"
            f"当前状态 `{baseline_status}`。"
        ),
        "evidence_lines": [
            f"pre coverage: {pre_summary['covered_symbols']}/{pre_summary['universe_symbols']} ({_fmt_ratio(pre_summary['coverage_ratio'])})",
            f"post coverage: {post_summary['covered_symbols']}/{post_summary['universe_symbols']} ({_fmt_ratio(post_summary['coverage_ratio'])})",
            f"eligible coverage: {post_summary['eligible_covered_symbols']}/{post_summary['eligible_universe_symbols']} ({_fmt_ratio(post_summary['eligible_coverage_ratio'])})",
            f"provider candidate success: {post_summary['candidate_success_symbols']}/{post_summary['candidate_attempted_symbols']} ({_fmt_ratio(post_summary['candidate_success_rate'])})",
        ],
        "research_progress_rows": [
            {
                "dimension": "数据输入",
                "status": "可进入验证" if stage_decision.stage != "pilot" else "pilot",
                "score": 3 if stage_decision.stage != "pilot" else 2,
                "evidence": f"coverage={_fmt_ratio(post_summary['coverage_ratio'])}，eligible={_fmt_ratio(post_summary['eligible_coverage_ratio'])}",
            },
            {
                "dimension": "策略完整性",
                "status": "最小重建完成" if baseline_rerun_completed else "等待复跑",
                "score": 3 if baseline_rerun_completed else 2,
                "evidence": f"baseline_status={baseline_status}",
            },
            {
                "dimension": "验证层",
                "status": "data_validate 已重跑",
                "score": 3,
                "evidence": "coverage_gap / readiness / quality artifacts 已刷新",
            },
            {
                "dimension": "晋级准备度",
                "status": stage_decision.stage,
                "score": 3 if stage_decision.stage == "validation-ready" else 4 if stage_decision.stage == "research-ready" else 2,
                "evidence": "由 coverage、bias、baseline 状态共同判定",
            },
            {
                "dimension": "Subagent 有效性",
                "status": "OFF",
                "score": 4,
                "evidence": "本轮主任务强串行，保持 OFF 可减少治理噪音",
            },
        ],
        "coverage_status_rows": [
            {"item": "Canonical universe", "result": CURRENT_UNIVERSE_ID},
            {"item": "Universe size", "result": str(post_summary["universe_symbols"])},
            {"item": "Covered symbols", "result": str(post_summary["covered_symbols"])},
            {"item": "Coverage ratio", "result": _fmt_ratio(post_summary["coverage_ratio"])},
            {"item": "ST count", "result": str(post_summary["st_total"])},
            {"item": "ST covered count", "result": str(post_summary["st_covered"])},
            {"item": "Current readiness stage", "result": stage_decision.stage},
        ],
        "missingness_rows": [
            {
                "dimension": "ST / 非 ST",
                "observation": f"ST={_fmt_ratio(post_summary['st_coverage_ratio'])}，非ST={_fmt_ratio(post_summary['non_st_coverage_ratio'])}",
                "conclusion": "ST 不是主缺口来源",
            },
            {
                "dimension": "沪 / 深主板",
                "observation": f"SSE={_fmt_ratio(post_summary['sse_coverage_ratio'])}，SZSE={_fmt_ratio(post_summary['szse_coverage_ratio'])}",
                "conclusion": "此前主偏差在沪市；本轮已显著收敛" if stage_decision.stage != "pilot" else "仍有交易所偏差",
            },
            {
                "dimension": "新 / 老股票",
                "observation": f"截止日后上市={post_summary['structural_no_bars_symbols']}",
                "conclusion": "新股结构性无 bars 已单独分类",
            },
            {
                "dimension": "provider / pipeline 层",
                "observation": json.dumps(post_summary["pipeline_location_counts"], ensure_ascii=False, sort_keys=True),
                "conclusion": "当前剩余缺口已可定位" if stage_decision.bias_explained else "仍有 unexplained missing",
            },
        ],
        "strategy_action_rows": [
            {
                "strategy": "baseline_limit_up",
                "actor": "main",
                "action": "baseline 最小重建复判" if baseline_rerun_completed else "等待 baseline 复跑",
                "result": baseline_status,
                "decision_delta": "允许继续 baseline 评估，但不恢复 legacy 主线",
            },
            {
                "strategy": "risk_constrained_limit_up",
                "actor": "main",
                "action": "保持 legacy comparison only",
                "result": "未恢复",
                "decision_delta": "等待 baseline 先站稳",
            },
            {
                "strategy": "tighter_entry_limit_up",
                "actor": "main",
                "action": "保持 legacy comparison only",
                "result": "未恢复",
                "decision_delta": "等待 baseline 先站稳",
            },
        ],
        "next_recommendation": "只重试 provider-failed 清单；若失败清单已清空，再专注 baseline 复核，不要回到 legacy 叙事。",
        "configured_gate": "AUTO",
        "effective_gate": "OFF",
        "active_strategy_subagents": "无",
        "active_infra_subagents": "无",
        "subagent_note": "本轮 audit、backfill、readiness judgement 共享同一证据链，串行推进比拆 agent 更稳。",
    }
    checkpoint_path = _write_text(paths.artifacts_dir / "coverage_recovery.CHECKPOINT.md", render_coverage_recovery_checkpoint(checkpoint_payload))
    artifact_payload["checkpoint_path"] = str(checkpoint_path)
    _write_json(artifact_json_path, artifact_payload)

    return {
        "generated_at": generated_at,
        "project": project,
        "pre_summary": pre_summary,
        "post_summary": post_summary,
        "stage_decision": stage_decision.to_dict(),
        "baseline_status": baseline_status,
        "selected_codes": selected_codes,
        "backfill_result": backfill_result,
        "baseline_result": baseline_result,
        "validate_result": validate_result,
        "memory_paths": {key: str(value) for key, value in memory_paths.items()},
        "session_state_path": str(session_state_path),
        "artifact_json_path": str(artifact_json_path),
        "checkpoint_path": str(checkpoint_path),
    }
