from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import load_config
from ..db import coverage_report, load_ohlcv_panel
from ..memory.ledger import stable_hash, to_jsonable
from ..project import resolve_project_paths
from ..selection import compute_start_point_scores, count_limit_up_history, filter_top_limit_up
from ..universe import load_universe_codes
from .models import (
    BranchPoolSnapshot,
    BranchPoolSpec,
    CoreUniverseSnapshot,
    CoreUniverseSpec,
    PoolExplanation,
    PoolMembershipDecision,
)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _normalize_codes(codes: list[str]) -> list[str]:
    return sorted({str(code).zfill(6) for code in codes if str(code).strip()})


def _default_core_spec(cfg: dict[str, Any]) -> CoreUniverseSpec:
    return CoreUniverseSpec(
        min_history_bars=max(160, int(cfg.get("min_bars", 160))),
    )


def _latest_snapshot_path(directory: Path, prefix: str) -> Path | None:
    if not directory.exists():
        return None
    matches = sorted(directory.glob(f"{prefix}*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2).rstrip() + "\n", encoding="utf-8")
    return path


def _load_symbols_metadata(paths) -> tuple[pd.DataFrame, Path | None]:
    symbols_path = paths.meta_dir / "symbols.csv"
    if not symbols_path.exists():
        return pd.DataFrame(), None
    frame = pd.read_csv(symbols_path, dtype={"code": str})
    if "code" in frame.columns:
        frame["code"] = frame["code"].astype(str).str.zfill(6)
    return frame, symbols_path


def _load_source_codes(paths) -> list[str]:
    symbols_frame, _ = _load_symbols_metadata(paths)
    if not symbols_frame.empty and "code" in symbols_frame.columns:
        codes = symbols_frame["code"].dropna().astype(str).str.zfill(6).tolist()
        if codes:
            return _normalize_codes(codes)
    return load_universe_codes(paths.project)


def _metadata_row(symbols_frame: pd.DataFrame, code: str) -> dict[str, Any]:
    if symbols_frame.empty or "code" not in symbols_frame.columns:
        return {}
    subset = symbols_frame.loc[symbols_frame["code"] == code]
    if subset.empty:
        return {}
    row = subset.iloc[0].to_dict()
    return {str(key): value for key, value in row.items()}


def _looks_like_mainboard(code: str) -> bool:
    return not (
        code.startswith("4")
        or code.startswith("8")
        or code.startswith("68")
        or code.startswith("300")
        or code.startswith("301")
    )


def _is_st_name(name: str | None) -> bool:
    value = str(name or "").upper()
    return "ST" in value or "*" in value or "退" in str(name or "")


def _load_listing_date(metadata: dict[str, Any]) -> pd.Timestamp | None:
    for key in ("listing_date", "list_date", "ipo_date"):
        value = metadata.get(key)
        if value in (None, "", "nan"):
            continue
        try:
            return pd.Timestamp(value)
        except Exception:
            return None
    return None


@dataclass(frozen=True)
class PoolBuildResult:
    snapshot: Any
    path: Path

    def __iter__(self):
        yield self.snapshot
        yield self.path


def build_core_universe_snapshot(
    *,
    project: str,
    cfg: dict[str, Any] | None = None,
    paths=None,
    config_path: Path | None = None,
    repo_root: Path | None = None,
    as_of_date: str | None = None,
) -> PoolBuildResult:
    if cfg is None or paths is None:
        cfg, paths = load_config(project, config_path=config_path)
    spec = _default_core_spec(cfg)
    source_codes = _load_source_codes(paths)
    symbols_frame, metadata_path = _load_symbols_metadata(paths)
    coverage = coverage_report(
        db_path=Path(str(cfg["db_path"])),
        freq=str(cfg["freq"]),
        codes=source_codes,
        data_mode="auto",
        end=as_of_date or cfg.get("end_date"),
    )
    coverage = coverage.set_index("code") if not coverage.empty else pd.DataFrame(index=_normalize_codes(source_codes))

    decisions: dict[str, PoolMembershipDecision] = {}
    eligible_for_liquidity: list[str] = []
    liquidity_values: dict[str, float] = {}
    end_date = as_of_date or cfg.get("end_date")

    for code in _normalize_codes(source_codes):
        metadata = _metadata_row(symbols_frame, code)
        reasons: list[str] = []
        notes: list[str] = []
        metrics: dict[str, Any] = {}

        board_value = str(metadata.get("board", "")).strip().lower()
        name_value = str(metadata.get("name", "")).strip()

        if board_value:
            metrics["board"] = board_value
            if "main" not in board_value and "主板" not in board_value:
                reasons.append("excluded_non_mainboard")
        elif not _looks_like_mainboard(code):
            reasons.append("excluded_non_mainboard_by_code")
        else:
            notes.append("board_metadata_unavailable")

        is_st = bool(metadata.get("is_st")) if "is_st" in metadata else _is_st_name(name_value)
        metrics["is_st"] = is_st
        if spec.exclude_st and is_st:
            reasons.append("excluded_st")
        elif spec.exclude_st and not metadata and not name_value:
            notes.append("st_metadata_unavailable")

        listing_date = _load_listing_date(metadata)
        if listing_date is not None and end_date:
            listing_days = int((pd.Timestamp(end_date) - listing_date).days)
            metrics["listing_days"] = listing_days
            if listing_days < spec.min_listing_days:
                reasons.append("excluded_new_listing")
        elif listing_date is None:
            notes.append("listing_date_unavailable")

        bars_count = int(coverage.loc[code, "bars_count"]) if code in coverage.index and "bars_count" in coverage.columns else 0
        last_date = str(coverage.loc[code, "last_date"]) if code in coverage.index and "last_date" in coverage.columns else None
        metrics["bars_count"] = bars_count
        metrics["last_bar_date"] = last_date
        if bars_count < spec.min_history_bars:
            reasons.append("excluded_insufficient_history")

        if reasons:
            decisions[code] = PoolMembershipDecision(
                code=code,
                included=False,
                reasons=reasons,
                metrics=metrics,
                notes=notes,
            )
            continue

        try:
            panels = load_ohlcv_panel(
                db_path=Path(str(cfg["db_path"])),
                freq=str(cfg["freq"]),
                codes=[code],
                start=cfg.get("start_date"),
                end=end_date,
                data_mode="auto",
            )
            close = panels["close"].get(code)
            volume = panels["volume"].get(code)
        except Exception:
            close = None
            volume = None

        if close is None or volume is None or close.dropna().empty:
            reasons.append("excluded_missing_panel")
            decisions[code] = PoolMembershipDecision(
                code=code,
                included=False,
                reasons=reasons,
                metrics=metrics,
                notes=notes,
            )
            continue

        recent_close = close.dropna().tail(spec.recent_volume_window)
        recent_volume = volume.reindex(recent_close.index).fillna(0.0).tail(spec.recent_volume_window)
        positive_ratio = float((recent_volume > 0).mean()) if len(recent_volume) > 0 else 0.0
        liquidity_proxy = float((recent_close.astype(float) * recent_volume.astype(float)).mean()) if len(recent_close) > 0 else 0.0
        metrics["positive_volume_ratio"] = round(positive_ratio, 4)
        metrics["liquidity_proxy"] = liquidity_proxy

        if positive_ratio < spec.min_positive_volume_ratio:
            reasons.append("excluded_thin_recent_volume")

        if reasons:
            decisions[code] = PoolMembershipDecision(
                code=code,
                included=False,
                reasons=reasons,
                metrics=metrics,
                notes=notes,
            )
            continue

        eligible_for_liquidity.append(code)
        liquidity_values[code] = liquidity_proxy
        decisions[code] = PoolMembershipDecision(
            code=code,
            included=True,
            reasons=["eligible_before_liquidity_cut"],
            metrics=metrics,
            notes=notes,
        )

    keep_count = max(1, int(math.ceil(len(eligible_for_liquidity) * spec.liquidity_keep_ratio))) if eligible_for_liquidity else 0
    ranked_by_liquidity = sorted(
        eligible_for_liquidity,
        key=lambda item: (-float(liquidity_values.get(item, 0.0)), item),
    )
    kept = set(ranked_by_liquidity[:keep_count])
    final_codes: list[str] = []

    for code, decision in list(decisions.items()):
        if not decision.included:
            continue
        metrics = dict(decision.metrics)
        metrics["liquidity_rank"] = ranked_by_liquidity.index(code) + 1 if code in ranked_by_liquidity else None
        metrics["liquidity_keep_count"] = keep_count
        if code not in kept:
            decisions[code] = PoolMembershipDecision(
                code=code,
                included=False,
                reasons=["excluded_low_liquidity"],
                metrics=metrics,
                notes=decision.notes,
            )
            continue
        final_codes.append(code)
        decisions[code] = PoolMembershipDecision(
            code=code,
            included=True,
            reasons=["included_core_pool"],
            metrics=metrics,
            notes=decision.notes,
        )

    snapshot_hash = stable_hash(
        {
            "spec": spec.to_dict(),
            "codes": final_codes,
            "as_of_date": end_date,
            "source_path": str(paths.universe_path),
        },
    )
    snapshot = CoreUniverseSnapshot(
        snapshot_id=f"core-{snapshot_hash[:12]}",
        generated_at=_utc_now(),
        as_of_date=str(end_date) if end_date else None,
        spec=spec,
        source_codes_path=str(paths.universe_path),
        metadata_path=str(metadata_path) if metadata_path else None,
        codes=final_codes,
        hash=snapshot_hash,
        decision_counts={
            "source_codes": len(source_codes),
            "included_codes": len(final_codes),
            "excluded_codes": len(source_codes) - len(final_codes),
        },
        decisions=decisions,
    )
    path = paths.core_pools_dir / f"{snapshot.snapshot_id}.json"
    _write_json(path, snapshot.to_dict())
    _write_json(paths.pools_dir / "latest_core_pool.json", snapshot.to_dict())
    return PoolBuildResult(snapshot=snapshot, path=path)


def build_branch_pool_snapshot(
    *,
    project: str,
    branch_id: str,
    hypothesis: str,
    cfg: dict[str, Any] | None = None,
    paths=None,
    config_path: Path | None = None,
    repo_root: Path | None = None,
    core_snapshot: CoreUniverseSnapshot | None = None,
    as_of_date: str | None = None,
    top_candidates: int | None = None,
) -> PoolBuildResult:
    if cfg is None or paths is None:
        cfg, paths = load_config(project, config_path=config_path)
    core = core_snapshot or load_latest_core_pool_snapshot(project, repo_root=repo_root, build_if_missing=True, config_path=config_path)
    if core is None:
        raise RuntimeError("Core universe snapshot is unavailable.")

    limit_days_window = int(cfg.get("limit_days_window", 60))
    top_pct_limit_up = float(cfg.get("top_pct_limit_up", 0.5))
    top_candidates = top_candidates or max(int(cfg.get("init_pool_size", 20)), int(cfg.get("stock_num", 6)) * int(cfg.get("topk_multiplier", 2)))
    spec = BranchPoolSpec(
        branch_id=branch_id,
        generator_id="limit_up_reaccumulation",
        strategy_mode=str(cfg.get("strategy_mode", "limit_up_screening")),
        limit_days_window=limit_days_window,
        top_pct_limit_up=top_pct_limit_up,
        top_candidates=int(top_candidates),
        hypothesis=hypothesis,
    )

    panels = load_ohlcv_panel(
        db_path=Path(str(cfg["db_path"])),
        freq=str(cfg["freq"]),
        codes=core.codes,
        start=cfg.get("start_date"),
        end=as_of_date or cfg.get("end_date"),
        data_mode="auto",
    )
    close = panels["close"].reindex(columns=core.codes).astype(float)
    open_df = panels["open"].reindex(columns=core.codes).astype(float)
    low_df = panels["low"].reindex(columns=core.codes).astype(float)
    volume = panels["volume"].reindex(columns=core.codes).astype(float)

    counts = count_limit_up_history(
        close=close,
        open_df=open_df,
        window=limit_days_window,
        threshold=float(cfg.get("limit_up_threshold", 0.095)),
    )
    limit_up_codes = filter_top_limit_up(core.codes, counts, top_pct=top_pct_limit_up)
    scores = compute_start_point_scores(
        close=close,
        open_df=open_df,
        low_df=low_df,
        codes=limit_up_codes,
        window=limit_days_window,
        threshold=float(cfg.get("limit_up_threshold", 0.095)),
    ).sort_values(ascending=True)

    branch_codes = [code for code in scores.index.tolist() if code in limit_up_codes][: int(top_candidates)]
    decisions: dict[str, PoolMembershipDecision] = {}
    for code in core.codes:
        metrics = {
            "limit_up_count": int(counts.get(code, 0)),
            "start_point_score": float(scores.get(code)) if code in scores.index else None,
            "volume_last": float(volume[code].dropna().iloc[-1]) if code in volume.columns and not volume[code].dropna().empty else None,
        }
        if code in branch_codes:
            decisions[code] = PoolMembershipDecision(
                code=code,
                included=True,
                reasons=["included_branch_pool"],
                metrics=metrics,
                notes=[],
            )
        elif code in limit_up_codes:
            decisions[code] = PoolMembershipDecision(
                code=code,
                included=False,
                reasons=["excluded_after_score_ranking"],
                metrics=metrics,
                notes=[],
            )
        else:
            decisions[code] = PoolMembershipDecision(
                code=code,
                included=False,
                reasons=["excluded_no_limit_up_history"],
                metrics=metrics,
                notes=[],
            )

    snapshot_hash = stable_hash(
        {
            "branch_id": branch_id,
            "core_snapshot_id": core.snapshot_id,
            "codes": branch_codes,
            "spec": spec.to_dict(),
            "as_of_date": as_of_date or cfg.get("end_date"),
        },
    )
    snapshot = BranchPoolSnapshot(
        snapshot_id=f"{branch_id}-{snapshot_hash[:12]}",
        generated_at=_utc_now(),
        as_of_date=str(as_of_date or cfg.get("end_date")) if (as_of_date or cfg.get("end_date")) else None,
        branch_id=branch_id,
        core_snapshot_id=core.snapshot_id,
        spec=spec,
        codes=branch_codes,
        hash=snapshot_hash,
        decision_counts={
            "core_input_codes": len(core.codes),
            "included_codes": len(branch_codes),
            "excluded_codes": len(core.codes) - len(branch_codes),
        },
        decisions=decisions,
    )
    path = paths.branch_pools_dir / f"{snapshot.snapshot_id}.json"
    _write_json(path, snapshot.to_dict())
    _write_json(paths.pools_dir / f"latest_branch_pool_{branch_id}.json", snapshot.to_dict())
    return PoolBuildResult(snapshot=snapshot, path=path)


def load_core_pool_snapshot(path: Path) -> CoreUniverseSnapshot:
    payload = json.loads(path.read_text(encoding="utf-8"))
    decisions = {
        code: PoolMembershipDecision(**item)
        for code, item in (payload.get("decisions") or {}).items()
    }
    return CoreUniverseSnapshot(
        snapshot_id=str(payload["snapshot_id"]),
        generated_at=str(payload["generated_at"]),
        as_of_date=payload.get("as_of_date"),
        spec=CoreUniverseSpec(**payload["spec"]),
        source_codes_path=str(payload["source_codes_path"]),
        metadata_path=payload.get("metadata_path"),
        codes=_normalize_codes(payload.get("codes", [])),
        hash=str(payload["hash"]),
        decision_counts=dict(payload.get("decision_counts", {})),
        decisions=decisions,
    )


def load_branch_pool_snapshot(path: Path) -> BranchPoolSnapshot:
    payload = json.loads(path.read_text(encoding="utf-8"))
    decisions = {
        code: PoolMembershipDecision(**item)
        for code, item in (payload.get("decisions") or {}).items()
    }
    return BranchPoolSnapshot(
        snapshot_id=str(payload["snapshot_id"]),
        generated_at=str(payload["generated_at"]),
        as_of_date=payload.get("as_of_date"),
        branch_id=str(payload["branch_id"]),
        core_snapshot_id=str(payload["core_snapshot_id"]),
        spec=BranchPoolSpec(**payload["spec"]),
        codes=_normalize_codes(payload.get("codes", [])),
        hash=str(payload["hash"]),
        decision_counts=dict(payload.get("decision_counts", {})),
        decisions=decisions,
    )


def load_latest_core_pool_snapshot(
    project: str,
    *,
    repo_root: Path | None = None,
    build_if_missing: bool = False,
    config_path: Path | None = None,
) -> CoreUniverseSnapshot | None:
    paths = resolve_project_paths(project, root=repo_root)
    latest = paths.pools_dir / "latest_core_pool.json"
    if latest.exists():
        return load_core_pool_snapshot(latest)
    latest = _latest_snapshot_path(paths.core_pools_dir, "core-")
    if latest is not None:
        return load_core_pool_snapshot(latest)
    if build_if_missing:
        return build_core_universe_snapshot(project=project, config_path=config_path, repo_root=repo_root).snapshot
    return None


def load_latest_branch_pool_snapshot(
    project: str,
    *,
    branch_id: str,
    repo_root: Path | None = None,
) -> BranchPoolSnapshot | None:
    paths = resolve_project_paths(project, root=repo_root)
    latest = paths.pools_dir / f"latest_branch_pool_{branch_id}.json"
    if latest.exists():
        return load_branch_pool_snapshot(latest)
    latest = _latest_snapshot_path(paths.branch_pools_dir, f"{branch_id}-")
    if latest is not None:
        return load_branch_pool_snapshot(latest)
    return None


def resolve_research_universe_codes(
    project: str,
    *,
    config_path: Path | None = None,
    repo_root: Path | None = None,
    build_if_missing: bool = True,
) -> tuple[list[str], str]:
    snapshot = load_latest_core_pool_snapshot(
        project,
        repo_root=repo_root,
        build_if_missing=build_if_missing,
        config_path=config_path,
    )
    if snapshot is not None and snapshot.codes:
        return list(snapshot.codes), snapshot.snapshot_id
    return load_universe_codes(project), "legacy_universe_codes"


def explain_pool_membership(
    *,
    project: str,
    code: str,
    kind: str,
    branch_id: str | None = None,
    repo_root: Path | None = None,
) -> PoolExplanation:
    normalized = str(code).zfill(6)
    if kind == "core":
        snapshot = load_latest_core_pool_snapshot(project, repo_root=repo_root, build_if_missing=True)
        if snapshot is None:
            raise RuntimeError("Core pool snapshot is unavailable.")
        decision = snapshot.decisions.get(normalized) or PoolMembershipDecision(
            code=normalized,
            included=False,
            reasons=["code_not_present_in_core_source"],
        )
        return PoolExplanation(
            project=project,
            kind="core",
            snapshot_id=snapshot.snapshot_id,
            code=normalized,
            included=decision.included,
            reasons=list(decision.reasons),
            metrics=dict(decision.metrics),
            notes=list(decision.notes),
        )
    if not branch_id:
        raise ValueError("branch_id is required when kind=branch")
    snapshot = load_latest_branch_pool_snapshot(project, branch_id=branch_id, repo_root=repo_root)
    if snapshot is None:
        raise RuntimeError(f"Branch pool snapshot is unavailable for branch {branch_id}.")
    decision = snapshot.decisions.get(normalized) or PoolMembershipDecision(
        code=normalized,
        included=False,
        reasons=["code_not_present_in_branch_input"],
    )
    return PoolExplanation(
        project=project,
        kind="branch",
        snapshot_id=snapshot.snapshot_id,
        code=normalized,
        included=decision.included,
        reasons=list(decision.reasons),
        metrics=dict(decision.metrics),
        notes=list(decision.notes),
    )


def build_pool_snapshot(
    *,
    project: str,
    kind: str,
    branch_id: str | None = None,
    config_path: Path | None = None,
    repo_root: Path | None = None,
    as_of_date: str | None = None,
) -> PoolBuildResult:
    if kind == "core":
        return build_core_universe_snapshot(
            project=project,
            config_path=config_path,
            repo_root=repo_root,
            as_of_date=as_of_date,
        )
    if not branch_id:
        raise ValueError("branch_id is required when kind=branch")
    core = load_latest_core_pool_snapshot(project, repo_root=repo_root, build_if_missing=True, config_path=config_path)
    if core is None:
        raise RuntimeError("Core universe snapshot is unavailable.")
    return build_branch_pool_snapshot(
        project=project,
        branch_id=branch_id,
        hypothesis=f"Branch pool build for {branch_id}",
        config_path=config_path,
        repo_root=repo_root,
        core_snapshot=core,
        as_of_date=as_of_date,
    )
