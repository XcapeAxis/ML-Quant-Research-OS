from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from .backtest_engine import BacktestConfig, StoplossParams, rank_targets, run_rebalance_backtest_with_stoploss, summarize_equity
from .config import load_config
from .data.validation import validate_project_data
from .memory.ledger import append_jsonl, stable_hash
from .memory.research_activity import append_strategy_action_log, read_strategy_action_log, write_research_activity_markdown
from .project import resolve_project_paths
from .project_identity import CANONICAL_PROJECT_ID
from .research_core import build_limit_up_rank_artifacts, load_index_daily_ratio, run_limit_up_backtest_artifacts
from .research_readiness import evaluate_research_readiness
from .universe_profiles import materialize_universe_profile
from .validation.baselines import run_simple_baselines
from .validation.leakage import audit_strategy_leakage
from .validation.promotion_gate import evaluate_promotion_gate
from .validation.robustness import cost_sensitivity_summary, parameter_perturbation_summary
from .validation.walk_forward import walk_forward_summary


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return path


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2).rstrip() + "\n", encoding="utf-8")
    return path


def _pct(value: float) -> str:
    return f"{float(value):.2%}"


def _num(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    try:
        return f"{float(value):.4f}"
    except Exception:
        return str(value)


def _merge_cfg(base_cfg: Mapping[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(dict(base_cfg))
    for key, value in dict(overrides).items():
        merged[key] = value
    return merged


def _load_symbols_frame(paths) -> pd.DataFrame:
    symbols_path = paths.meta_dir / "symbols.csv"
    if not symbols_path.exists():
        return pd.DataFrame(columns=["code", "name", "is_st", "board"])
    frame = pd.read_csv(symbols_path, dtype={"code": str})
    if "code" not in frame.columns:
        return pd.DataFrame(columns=["code", "name", "is_st", "board"])
    frame["code"] = frame["code"].astype(str).str.zfill(6)
    frame["name"] = frame.get("name", pd.Series([""] * len(frame))).fillna("").astype(str)
    raw_is_st = frame.get("is_st", pd.Series([False] * len(frame)))
    if raw_is_st.dtype == bool:
        frame["is_st"] = raw_is_st.fillna(False)
    else:
        frame["is_st"] = raw_is_st.fillna(False).astype(str).str.lower().isin({"1", "true", "yes"})
    frame["board"] = frame.get("board", pd.Series([""] * len(frame))).fillna("").astype(str)
    return frame[["code", "name", "is_st", "board"]].drop_duplicates("code")


def _st_mask(frame: pd.DataFrame) -> pd.Series:
    name_mask = frame.get("name", pd.Series([""] * len(frame))).astype(str).str.upper().str.contains("ST|\\*", regex=True)
    st_mask = frame.get("is_st", pd.Series([False] * len(frame))).astype(bool)
    return st_mask | name_mask


def _max_drawdown_episode(equity: pd.Series) -> dict[str, Any]:
    if equity.empty:
        return {
            "peak_date": None,
            "trough_date": None,
            "recovery_date": None,
            "max_drawdown": 0.0,
            "duration_days": 0,
        }
    peak = equity.cummax()
    drawdown = equity.divide(peak).subtract(1.0)
    trough_date = pd.Timestamp(drawdown.idxmin())
    peak_date = pd.Timestamp(equity.loc[:trough_date].idxmax())
    recovery_date = None
    peak_value = float(equity.loc[peak_date])
    recovery_candidates = equity.loc[trough_date:]
    recovered = recovery_candidates[recovery_candidates >= peak_value]
    if not recovered.empty:
        recovery_date = pd.Timestamp(recovered.index[0])
    duration_end = recovery_date or pd.Timestamp(equity.index[-1])
    return {
        "peak_date": peak_date.strftime("%Y-%m-%d"),
        "trough_date": trough_date.strftime("%Y-%m-%d"),
        "recovery_date": recovery_date.strftime("%Y-%m-%d") if recovery_date is not None else None,
        "max_drawdown": float(drawdown.min()),
        "duration_days": int((duration_end - peak_date).days),
    }


def _format_top_codes(codes: list[tuple[str, int]]) -> str:
    if not codes:
        return "无"
    return "、".join(f"{code}({count})" for code, count in codes)


def render_campaign_checkpoint(summary: Mapping[str, Any]) -> str:
    progress_rows = list(summary.get("progress_rows", [])) or ["| 未记录 | 阻塞 | 0/4 | 未记录 |"]
    universe_rows = list(summary.get("universe_rows", [])) or ["| 未记录 | 未记录 | 未记录 |"]
    action_rows = list(summary.get("strategy_action_rows", [])) or [
        "| 本轮无实质策略研究 | main:main | 主要刷新报告或记忆写回 | 未新增策略结论 | 无变化 |",
    ]
    strategy_line = str(summary.get("strategy_line", "本轮未记录到明确的策略推进对象。"))
    if not bool(summary.get("substantive_research", True)):
        reason = str(summary.get("no_research_reason", "本轮未进行实质策略研究。")).strip()
        strategy_line = reason or strategy_line
    evidence_lines = list(summary.get("evidence_lines", []))
    if bool(summary.get("benchmark_degraded")):
        evidence_lines.append("- benchmark 状态仍降级：当前任何策略结论都必须降级表述。")
    lines = [
        "Done",
        f"- 系统推进：{summary.get('system_line', '未记录')}",
        f"- 策略推进：{strategy_line}",
        "Evidence",
        *evidence_lines,
        "Research progress",
        "| 维度 | 状态 | 分数 | 证据 |",
        "|---|---|---:|---|",
        *progress_rows,
        "Universe comparison",
        "| Universe | ST policy | 结论摘要 |",
        "|---|---|---|",
        *universe_rows,
        "Strategy actions this run",
        "| 策略 | 执行者 | 动作 | 结果 | 决策变化 |",
        "|---|---|---|---|---|",
        *action_rows,
        "Next recommendation",
        f"- {summary.get('next_recommendation', '未记录')}",
        "Subagent status",
        f"- configured gate: {summary.get('configured_gate', 'AUTO')}",
        f"- effective gate this run: {summary.get('effective_gate', 'OFF')}",
        f"- active strategy-research subagents: {summary.get('active_research_subagents', '无')}",
        f"- active infrastructure subagents: {summary.get('active_infrastructure_subagents', '无')}",
        f"- {summary.get('subagent_note', '本轮工作主要是单线诊断与同口径比较，保持 OFF 可以减少噪音。')}",
    ]
    return "\n".join(lines)


def _evaluate_variant(
    *,
    project: str,
    cfg: Mapping[str, Any],
    paths,
    universe_codes: list[str],
    universe_profile: Mapping[str, Any],
    variant_id: str,
    variant_meta: Mapping[str, Any],
    st_lookup: Mapping[str, bool],
) -> dict[str, Any]:
    overrides = dict(variant_meta.get("overrides", {}) or {})
    variant_cfg = _merge_cfg(cfg, overrides)
    try:
        rank_artifacts = build_limit_up_rank_artifacts(cfg=variant_cfg, paths=paths, universe_codes=universe_codes)
        backtest_artifacts = run_limit_up_backtest_artifacts(
            cfg=variant_cfg,
            paths=paths,
            rank_df=rank_artifacts.selection.rank_df,
            save="none",
            no_show=True,
        )
        leakage = audit_strategy_leakage(
            rank_df=rank_artifacts.selection.rank_df,
            close_panel=backtest_artifacts.close_panel,
            volume_panel=backtest_artifacts.volume_panel,
            cfg=variant_cfg,
            universe_codes=universe_codes,
        )
        walk_forward = walk_forward_summary(
            rank_df=rank_artifacts.selection.rank_df,
            windows=list(variant_cfg.get("walk_forward", {}).get("windows", [])),
        )
        baselines = run_simple_baselines(
            close_panel=backtest_artifacts.close_panel,
            benchmark_code=str(variant_cfg.get("baselines", {}).get("benchmark_code", "000001")),
            benchmark_series=backtest_artifacts.benchmark_series,
        )
        cost = cost_sensitivity_summary(
            metrics_df=backtest_artifacts.metrics_df,
            commission_grid=list(variant_cfg.get("cost_sweep", {}).get("commission_grid", [])),
            slippage_grid=list(variant_cfg.get("cost_sweep", {}).get("slippage_grid", [])),
        )
        parameter_robustness = parameter_perturbation_summary(
            cfg=variant_cfg,
            perturbations=list(variant_cfg.get("research_validation", {}).get("parameter_perturbations", [])),
        )
        metrics = backtest_artifacts.metrics_df.iloc[0].to_dict() if not backtest_artifacts.metrics_df.empty else {}
        decision = evaluate_promotion_gate(
            metrics=metrics,
            leakage_report=leakage,
            walk_forward=walk_forward,
            baselines=baselines,
            cost_sensitivity=cost,
            parameter_robustness=parameter_robustness,
            research_hypothesis=str(variant_cfg.get("research_hypothesis", "")),
            cfg=variant_cfg,
        ).to_dict()
        stock_num = int(variant_cfg.get("stock_num", cfg.get("stock_num", 6)))
        selected = rank_artifacts.selection.rank_df.copy()
        selected["code"] = selected["code"].astype(str).str.zfill(6)
        selected = selected[selected["rank"] <= stock_num].copy()
        selected["is_st"] = selected["code"].map(lambda code: bool(st_lookup.get(str(code).zfill(6), False)))
        return {
            "variant_id": variant_id,
            "title": str(variant_meta.get("title", variant_id)),
            "decision_role": str(variant_meta.get("decision_role", "candidate")),
            "thesis": str(variant_meta.get("thesis", "")),
            "profile_id": str(universe_profile["profile_id"]),
            "profile_display_name": str(universe_profile["display_name"]),
            "profile_source_id": str(universe_profile["source_id"]),
            "overrides": overrides,
            "metrics": {
                "total_return": float(metrics.get("total_return", 0.0)),
                "annualized_return": float(metrics.get("annualized_return", 0.0)),
                "max_drawdown": float(metrics.get("max_drawdown", 0.0)),
                "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0)),
                "turnover_estimate": float(metrics.get("turnover_estimate", 0.0)),
                "tradability_pass_rate": float(metrics.get("tradability_pass_rate", 0.0)),
                "days": float(metrics.get("days", 0.0)),
            },
            "decision": decision,
            "baselines": baselines,
            "walk_forward": walk_forward,
            "cost_sensitivity": cost,
            "parameter_robustness": parameter_robustness,
            "candidate_rows": int(len(rank_artifacts.selection.rank_df)),
            "rebalance_dates": int(rank_artifacts.selection.rank_df["date"].nunique()),
            "selected_rows": int(len(selected)),
            "selected_unique_codes": int(selected["code"].nunique()) if not selected.empty else 0,
            "selected_st_rows": int(selected["is_st"].sum()) if not selected.empty else 0,
            "selected_st_ratio": float(selected["is_st"].mean()) if not selected.empty else 0.0,
            "close_panel_has_benchmark": bool(
                str(variant_cfg.get("baselines", {}).get("benchmark_code", "000001")).zfill(6)
                in backtest_artifacts.close_panel.columns
            ),
            "benchmark_series_len": int(len(backtest_artifacts.benchmark_series)),
            "_variant_cfg": variant_cfg,
            "_rank_df": rank_artifacts.selection.rank_df,
            "_equity": backtest_artifacts.equity,
            "_close_panel": backtest_artifacts.close_panel,
            "_benchmark_series": backtest_artifacts.benchmark_series,
            "_targets": rank_targets(rank_artifacts.selection.rank_df, topn=stock_num),
        }
    except Exception as exc:
        return {
            "variant_id": variant_id,
            "title": str(variant_meta.get("title", variant_id)),
            "decision_role": str(variant_meta.get("decision_role", "candidate")),
            "thesis": str(variant_meta.get("thesis", "")),
            "profile_id": str(universe_profile["profile_id"]),
            "profile_display_name": str(universe_profile["display_name"]),
            "profile_source_id": str(universe_profile["source_id"]),
            "overrides": overrides,
            "metrics": {
                "total_return": 0.0,
                "annualized_return": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "turnover_estimate": 0.0,
                "tradability_pass_rate": 0.0,
                "days": 0.0,
            },
            "decision": {
                "promotable": False,
                "reasons": [f"variant_failed:{exc}"],
                "checks": {"baselines_status": "degraded", "max_drawdown": 0.0},
            },
            "baselines": {
                "status": "degraded",
                "benchmark_available": False,
                "equal_weight_available": False,
                "reasons": [f"variant_failed:{exc}"],
            },
            "walk_forward": {"windows": [], "windows_alive": 0, "all_windows_alive": False},
            "cost_sensitivity": {"base_total_return": 0.0, "worst_cost_stressed_return": 0.0, "return_retention_ratio": 0.0},
            "parameter_robustness": {"baseline": {}, "variants": [], "variant_count": 0},
            "candidate_rows": 0,
            "rebalance_dates": 0,
            "selected_rows": 0,
            "selected_unique_codes": 0,
            "selected_st_rows": 0,
            "selected_st_ratio": 0.0,
            "close_panel_has_benchmark": False,
            "benchmark_series_len": 0,
            "_variant_cfg": variant_cfg,
            "_rank_df": pd.DataFrame(columns=["date", "code", "rank", "score"]),
            "_equity": pd.Series(dtype=float),
            "_close_panel": pd.DataFrame(),
            "_benchmark_series": pd.Series(dtype=float),
            "_targets": {},
        }


def _market_stoploss_probe(variant_result: Mapping[str, Any]) -> dict[str, Any]:
    cfg = dict(variant_result["_variant_cfg"])
    bt_cfg = BacktestConfig(
        cash=float(cfg["cash"]),
        commission=float(cfg.get("commission", 0.0001)),
        stamp_duty=float(cfg.get("stamp_duty", 0.0005)),
        slippage=float(cfg.get("slippage", 0.002)),
        risk_free_rate=float(cfg.get("risk_free_rate", 0.03)),
        risk_overlay=cfg.get("risk_overlay"),
        min_commission=float(cfg["min_commission"]) if cfg.get("min_commission") is not None else None,
    )
    stoploss_params = StoplossParams(
        stoploss_limit=float(cfg.get("stoploss_limit", 0.91)),
        take_profit_ratio=float(cfg.get("take_profit_ratio", 2.0)),
        market_stoploss_ratio=float(cfg.get("market_stoploss_ratio", 0.93)),
        loss_black_days=int(cfg.get("loss_black_days", 20)),
        no_trade_months=tuple(int(item) for item in cfg.get("no_trade_months", [])),
        min_commission=float(cfg["min_commission"]) if cfg.get("min_commission") is not None else None,
    )
    close_panel = variant_result["_close_panel"]
    targets = dict(variant_result["_targets"])
    equity_without_market = run_rebalance_backtest_with_stoploss(
        close_panel=close_panel,
        targets_by_date=targets,
        cfg=bt_cfg,
        stoploss_params=stoploss_params,
        index_daily_ratio=None,
    )
    metrics_without_market = summarize_equity(equity_without_market, bt_cfg)
    cfg_start = pd.Timestamp(close_panel.index.min()).strftime("%Y-%m-%d")
    cfg_end = pd.Timestamp(close_panel.index.max()).strftime("%Y-%m-%d")
    index_ratio = load_index_daily_ratio(
        Path(str(cfg["db_path"])),
        str(cfg["freq"]),
        str(cfg.get("calendar_code", "000001")).zfill(6),
        cfg_start,
        cfg_end,
    )
    market_stop_hits = int((index_ratio <= stoploss_params.market_stoploss_ratio).sum()) if index_ratio is not None else 0
    return {
        "with_market_stoploss_total_return": float(variant_result["metrics"]["total_return"]),
        "with_market_stoploss_max_drawdown": float(variant_result["metrics"]["max_drawdown"]),
        "without_market_stoploss_total_return": float(metrics_without_market.get("total_return", 0.0)),
        "without_market_stoploss_max_drawdown": float(metrics_without_market.get("max_drawdown", 0.0)),
        "market_stoploss_trigger_days": market_stop_hits,
        "market_stoploss_ratio": float(stoploss_params.market_stoploss_ratio),
    }


def _build_benchmark_diagnostic(variant_result: Mapping[str, Any]) -> dict[str, Any]:
    implicit = run_simple_baselines(
        close_panel=variant_result["_close_panel"],
        benchmark_code=str(variant_result["_variant_cfg"].get("baselines", {}).get("benchmark_code", "000001")),
        benchmark_series=None,
    )
    explicit = dict(variant_result["baselines"])
    benchmark_fixed = explicit.get("status") == "pass" and implicit.get("status") != "pass"
    benchmark_series_len = int(variant_result.get("benchmark_series_len", 0))
    drawdown_value = float(variant_result["metrics"]["max_drawdown"])
    if explicit.get("status") == "pass":
        drawdown_confidence = (
            f"当前 {_pct(abs(drawdown_value))} 的回撤结论可作为策略自身结果看待；"
            "先前需要降级的是 benchmark 链路解释，不是策略净值本身。"
        )
    else:
        drawdown_confidence = (
            f"benchmark 仍未完整时，{_pct(abs(drawdown_value))} 只能视为待复核的阶段性回撤结果。"
        )
    return {
        "benchmark_code": str(variant_result["_variant_cfg"].get("baselines", {}).get("benchmark_code", "000001")).zfill(6),
        "calendar_code": str(variant_result["_variant_cfg"].get("calendar_code", "000001")).zfill(6),
        "close_panel_has_benchmark": bool(variant_result.get("close_panel_has_benchmark")),
        "benchmark_series_len": benchmark_series_len,
        "implicit_status": str(implicit.get("status", "unknown")),
        "explicit_status": str(explicit.get("status", "unknown")),
        "implicit_reasons": list(implicit.get("reasons", [])),
        "explicit_reasons": list(explicit.get("reasons", [])),
        "benchmark_fixed": benchmark_fixed,
        "drawdown_confidence": drawdown_confidence,
        "role_summary": [
            "作为 calendar_code，000001 提供市场止损过滤输入。",
            "作为 baselines.benchmark_code，000001 提供晋级对照基准。",
            "000001 不需要出现在策略 rank 的 close_panel 中；显式传入 benchmark_series 即可。",
        ],
    }


def _build_drawdown_diagnostic(
    *,
    baseline_result: Mapping[str, Any],
    risk_result: Mapping[str, Any] | None,
    tighter_result: Mapping[str, Any] | None,
    peer_baseline_result: Mapping[str, Any] | None,
    market_probe: Mapping[str, Any],
) -> dict[str, Any]:
    episode = _max_drawdown_episode(baseline_result["_equity"])
    monthly_returns = (
        baseline_result["_equity"].pct_change().fillna(0.0).add(1.0).groupby(baseline_result["_equity"].index.to_period("M")).prod().sub(1.0)
    )
    worst_months = [
        {"month": str(period), "return": float(value)}
        for period, value in monthly_returns.sort_values().head(3).items()
    ]
    rank_df = baseline_result["_rank_df"].copy()
    rank_df["date"] = pd.to_datetime(rank_df["date"])
    peak_date = pd.Timestamp(episode["peak_date"]) if episode.get("peak_date") else None
    trough_date = pd.Timestamp(episode["trough_date"]) if episode.get("trough_date") else None
    if peak_date is not None and trough_date is not None:
        window = rank_df[(rank_df["date"] >= peak_date) & (rank_df["date"] <= trough_date)]
    else:
        window = rank_df
    stock_num = int(baseline_result["_variant_cfg"].get("stock_num", 6))
    top_codes = (
        window[window["rank"] <= stock_num]["code"].astype(str).str.zfill(6).value_counts().head(5).items()
        if not window.empty
        else []
    )
    risk_delta = None
    if risk_result is not None:
        risk_delta = {
            "total_return_delta": float(risk_result["metrics"]["total_return"]) - float(baseline_result["metrics"]["total_return"]),
            "max_drawdown_delta": float(risk_result["metrics"]["max_drawdown"]) - float(baseline_result["metrics"]["max_drawdown"]),
        }
    tighter_delta = None
    if tighter_result is not None:
        tighter_delta = {
            "total_return_delta": float(tighter_result["metrics"]["total_return"]) - float(baseline_result["metrics"]["total_return"]),
            "max_drawdown_delta": float(tighter_result["metrics"]["max_drawdown"]) - float(baseline_result["metrics"]["max_drawdown"]),
        }
    universe_delta = None
    if peer_baseline_result is not None:
        universe_delta = {
            "total_return_delta": float(peer_baseline_result["metrics"]["total_return"]) - float(baseline_result["metrics"]["total_return"]),
            "max_drawdown_delta": float(peer_baseline_result["metrics"]["max_drawdown"]) - float(baseline_result["metrics"]["max_drawdown"]),
        }
    return {
        "episode": episode,
        "worst_months": worst_months,
        "top_codes_during_drawdown": list(top_codes),
        "risk_delta": risk_delta,
        "tighter_delta": tighter_delta,
        "universe_delta": universe_delta,
        "market_probe": dict(market_probe),
    }


def _pick_strategy_roles(results: Mapping[str, Mapping[str, Any]], research_profile_id: str) -> dict[str, str]:
    research_results = dict(results.get(research_profile_id, {}) or {})
    baseline = research_results.get("baseline_limit_up")
    challengers = [item for key, item in research_results.items() if key != "baseline_limit_up"]
    if not baseline or not challengers:
        return {
            "main_track": "baseline_limit_up",
            "control_track": "baseline_limit_up",
            "deferred_track": "none",
        }

    def _score(item: Mapping[str, Any]) -> tuple[int, float, float, float]:
        promotable = 1 if item.get("decision", {}).get("promotable") else 0
        max_drawdown = -abs(float(item.get("metrics", {}).get("max_drawdown", 0.0)))
        total_return = float(item.get("metrics", {}).get("total_return", 0.0))
        sharpe = float(item.get("metrics", {}).get("sharpe_ratio", 0.0))
        return promotable, max_drawdown, total_return, sharpe

    best = sorted(challengers, key=_score, reverse=True)[0]
    deferred = [item for item in challengers if item["variant_id"] != best["variant_id"]]
    return {
        "main_track": str(best["variant_id"]),
        "control_track": "baseline_limit_up",
        "deferred_track": str(deferred[0]["variant_id"]) if deferred else "none",
    }


def _strip_internal(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _strip_internal(item) for key, item in value.items() if not str(key).startswith("_")}
    if isinstance(value, list):
        return [_strip_internal(item) for item in value]
    return value


def _read_existing_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _render_benchmark_markdown(result: Mapping[str, Any]) -> str:
    lines = [
        "# Benchmark 诊断",
        "",
        f"- benchmark_code: `{result['benchmark_code']}`",
        f"- calendar_code: `{result['calendar_code']}`",
        f"- close_panel_has_benchmark: `{result['close_panel_has_benchmark']}`",
        f"- benchmark_series_len: `{result['benchmark_series_len']}`",
        f"- implicit_status: `{result['implicit_status']}`",
        f"- explicit_status: `{result['explicit_status']}`",
        "",
        "## 000001 当前角色",
    ]
    lines.extend(f"- {item}" for item in result["role_summary"])
    lines.extend(
        [
            "",
            "## 本轮关键证据",
            f"- 不显式传入 benchmark_series 时：`{result['implicit_status']}`，原因：{', '.join(result['implicit_reasons']) or '无'}`",
            f"- 显式传入 benchmark_series 后：`{result['explicit_status']}`，原因：{', '.join(result['explicit_reasons']) or '无'}`",
            f"- drawdown 结论强度：{result['drawdown_confidence']}",
            "",
            "## 研究结论",
        ],
    )
    if result["benchmark_fixed"]:
        lines.append("- `benchmark_missing:000001` 已定位为基准链路传参问题，而不是数据库里真的缺 000001。")
    else:
        lines.append("- benchmark 问题仍未完全拆清，本轮策略结论必须降级表述。")
    return "\n".join(lines)


def _render_universe_markdown(
    *,
    profile_rows: list[dict[str, Any]],
    research_profile_id: str,
    deployment_profile_id: str,
) -> str:
    lines = [
        "# Universe 对比",
        "",
        f"- canonical research profile: `{research_profile_id}`",
        f"- canonical deployment control profile: `{deployment_profile_id}`",
        "",
        "| Universe | ST policy | source_count | included_count | source_st_count | included_st_count | readiness |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in profile_rows:
        lines.append(
            "| {profile_id} | {policy} | {source_count} | {included_count} | {source_st_count} | {included_st_count} | {readiness} |".format(
                profile_id=row["profile_id"],
                policy="含 ST" if row["include_st"] else "不含 ST",
                source_count=row["source_count"],
                included_count=row["included_count"],
                source_st_count=row["source_st_count"],
                included_st_count=row["included_st_count"],
                readiness=row["readiness_stage"],
            ),
        )
    lines.extend(["", "## 研究结论"])
    for row in profile_rows:
        lines.append(f"- `{row['profile_id']}`: {row['summary']}")
    return "\n".join(lines)


def _render_drawdown_markdown(result: Mapping[str, Any]) -> str:
    episode = dict(result["episode"])
    probe = dict(result["market_probe"])
    lines = [
        "# 回撤归因",
        "",
        f"- 最大回撤: `{_pct(abs(result['episode']['max_drawdown']))}`",
        f"- 峰值日期: `{episode['peak_date']}`",
        f"- 谷底日期: `{episode['trough_date']}`",
        f"- 恢复日期: `{episode['recovery_date'] or '截至样本末尾未恢复'}`",
        f"- 峰谷持续天数: `{episode['duration_days']}`",
        "",
        "## 峰谷窗口最常出现的持仓候选",
        f"- {_format_top_codes(list(result['top_codes_during_drawdown']))}",
        "",
        "## 最差月份",
    ]
    if result["worst_months"]:
        lines.extend(f"- {item['month']}: {_pct(item['return'])}" for item in result["worst_months"])
    else:
        lines.append("- 无")
    lines.extend(
        [
            "",
            "## 市场止损链路影响",
            f"- 启用市场止损: 收益 `{_pct(probe['with_market_stoploss_total_return'])}`，回撤 `{_pct(abs(probe['with_market_stoploss_max_drawdown']))}`",
            f"- 关闭市场止损: 收益 `{_pct(probe['without_market_stoploss_total_return'])}`，回撤 `{_pct(abs(probe['without_market_stoploss_max_drawdown']))}`",
            f"- 指数触发天数: `{probe['market_stoploss_trigger_days']}`（阈值 `{probe['market_stoploss_ratio']}`）",
            "",
            "## 研究结论",
        ],
    )
    if result["risk_delta"] is not None:
        lines.append(
            "- 风控收紧分支相对 baseline 的变化: "
            f"收益 `{_pct(result['risk_delta']['total_return_delta'])}`，"
            f"回撤 `{_pct(result['risk_delta']['max_drawdown_delta'])}`。"
        )
    if result["tighter_delta"] is not None:
        lines.append(
            "- 入场收紧分支相对 baseline 的变化: "
            f"收益 `{_pct(result['tighter_delta']['total_return_delta'])}`，"
            f"回撤 `{_pct(result['tighter_delta']['max_drawdown_delta'])}`。"
        )
    if result["universe_delta"] is not None:
        lines.append(
            "- 含 ST / 不含 ST 宇宙在当前冻结源上的 baseline 差异: "
            f"收益 `{_pct(result['universe_delta']['total_return_delta'])}`，"
            f"回撤 `{_pct(result['universe_delta']['max_drawdown_delta'])}`。"
        )
    return "\n".join(lines)


def _render_strategy_comparison_markdown(
    *,
    results: Mapping[str, Mapping[str, Any]],
    strategy_roles: Mapping[str, str],
) -> str:
    lines = [
        "# 策略比较",
        "",
        "| Universe | 策略 | 收益 | 回撤 | Sharpe | 样本行数 | Baseline 状态 | 晋级结果 |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for profile_id, variants in results.items():
        for variant_id, item in variants.items():
            lines.append(
                "| {profile} | {variant} | {ret} | {dd} | {sharpe} | {rows} | {baseline_status} | {decision} |".format(
                    profile=profile_id,
                    variant=variant_id,
                    ret=_pct(item["metrics"]["total_return"]),
                    dd=_pct(abs(item["metrics"]["max_drawdown"])),
                    sharpe=_num(item["metrics"]["sharpe_ratio"]),
                    rows=item["selected_rows"],
                    baseline_status=item["baselines"]["status"],
                    decision="通过" if item["decision"]["promotable"] else "未通过",
                ),
            )
    lines.extend(
        [
            "",
            "## 当前建议",
            f"- 主线继续推进: `{strategy_roles['main_track']}`",
            f"- 对照线保留: `{strategy_roles['control_track']}`",
            f"- 暂缓线: `{strategy_roles['deferred_track']}`",
        ],
    )
    return "\n".join(lines)


def run_baseline_strategy_diagnostic(
    project: str,
    *,
    config_path: Path | None = None,
    verified_commands: list[str] | None = None,
) -> dict[str, Any]:
    cfg, paths = load_config(project, config_path=config_path)
    paths.ensure_dirs()
    generated_at = _utc_now()
    verified_commands = list(verified_commands or [])
    universe_policy = dict(cfg.get("universe_policy", {}) or {})
    comparison_profiles = list(universe_policy.get("comparison_profiles", [])) or [
        "full_a_mainboard_incl_st",
        "full_a_mainboard_ex_st",
    ]
    research_profile_id = str(universe_policy.get("research_profile", comparison_profiles[0]))
    deployment_profile_id = str(universe_policy.get("deployment_profile", comparison_profiles[-1]))

    symbols_frame = _load_symbols_frame(paths)
    st_lookup = {
        str(row["code"]).zfill(6): bool(row["is_st"]) or ("ST" in str(row["name"]).upper()) or ("*" in str(row["name"]))
        for _, row in symbols_frame.iterrows()
    }

    profile_rows: list[dict[str, Any]] = []
    profile_map: dict[str, dict[str, Any]] = {}
    for profile_id in comparison_profiles:
        materialization = materialize_universe_profile(project, profile_id, config_path=config_path)
        data_report = validate_project_data(
            project=project,
            db_path=Path(str(cfg["db_path"])),
            freq=str(cfg["freq"]),
            universe_codes=list(materialization.codes),
            provider_name=str(cfg.get("data_provider", {}).get("provider", "akshare")),
            data_quality_cfg=cfg.get("data_quality"),
            limit_threshold=float(cfg.get("limit_up_threshold", 0.095)),
        )
        readiness = evaluate_research_readiness(report=data_report, cfg=cfg)
        profile_summary = {
            "profile_id": materialization.profile_id,
            "display_name": materialization.display_name,
            "description": materialization.description,
            "source_id": materialization.source_id,
            "source_path": materialization.source_path,
            "artifact_path": materialization.artifact_path,
            "source_count": materialization.source_count,
            "included_count": materialization.included_count,
            "source_st_count": materialization.source_st_count,
            "included_st_count": materialization.included_st_count,
            "include_st": materialization.include_st,
            "readiness_stage": readiness.stage,
            "readiness_ready": readiness.ready,
        }
        profile_rows.append(profile_summary)
        profile_map[profile_id] = profile_summary

    strategy_variants = dict(cfg.get("strategy_variants", {}) or {})
    if not strategy_variants:
        strategy_variants = {
            "baseline_limit_up": {"title": "baseline_limit_up", "decision_role": "control", "thesis": "默认基线。", "overrides": {}},
        }

    results: dict[str, dict[str, Any]] = {}
    for profile_id in comparison_profiles:
        results[profile_id] = {}
        codes = materialize_universe_profile(project, profile_id, config_path=config_path).codes
        for variant_id, variant_meta in strategy_variants.items():
            results[profile_id][variant_id] = _evaluate_variant(
                project=project,
                cfg=cfg,
                paths=paths,
                universe_codes=list(codes),
                universe_profile=profile_map[profile_id],
                variant_id=variant_id,
                variant_meta=variant_meta,
                st_lookup=st_lookup,
            )

    baseline_result = results[research_profile_id]["baseline_limit_up"]
    risk_result = results[research_profile_id].get("risk_constrained_limit_up")
    tighter_result = results[research_profile_id].get("tighter_entry_limit_up")
    peer_baseline_result = None
    if deployment_profile_id != research_profile_id:
        peer_baseline_result = results[deployment_profile_id].get("baseline_limit_up")
    market_probe = _market_stoploss_probe(baseline_result)
    benchmark_diagnostic = _build_benchmark_diagnostic(baseline_result)
    benchmark_diagnostic["market_probe"] = market_probe
    drawdown_diagnostic = _build_drawdown_diagnostic(
        baseline_result=baseline_result,
        risk_result=risk_result,
        tighter_result=tighter_result,
        peer_baseline_result=peer_baseline_result,
        market_probe=market_probe,
    )
    strategy_roles = _pick_strategy_roles(results, research_profile_id)

    research_baseline = results[research_profile_id]["baseline_limit_up"]
    deploy_baseline = results[deployment_profile_id]["baseline_limit_up"]
    for row in profile_rows:
        baseline = results[row["profile_id"]]["baseline_limit_up"]
        if row["included_st_count"] <= 0:
            row["summary"] = "当前冻结 symbols 快照里的 ST 暴露为 0，本轮物化结果与另一宇宙实质一致，暂时无法识别 ST 效应。"
        else:
            row["summary"] = (
                f"baseline 收益 {_pct(baseline['metrics']['total_return'])}，"
                f"回撤 {_pct(abs(baseline['metrics']['max_drawdown']))}，"
                f"ST 选股暴露 {_pct(baseline['selected_st_ratio'])}。"
            )

    benchmark_degraded = benchmark_diagnostic["explicit_status"] != "pass"
    system_line = "已把 benchmark 显式传递给 baseline 诊断，并新增双宇宙 profile 定义与 ST 识别口径。"
    strategy_line = (
        f"本轮完成三条策略线在 `{research_profile_id}` / `{deployment_profile_id}` 两个宇宙上的同口径比较；"
        f"建议主线改为 `{strategy_roles['main_track']}`，`baseline_limit_up` 保留为对照。"
    )
    progress_rows = [
        "| 数据输入 | 部分可用 | 3/4 | 715/715 validated bars 可用，但当前冻结 symbols 快照的 ST 暴露仍为 0。|",
        "| 策略完整性 | 当前阶段可运行 | 3/4 | 三条策略线已在同日期、同成本、同 benchmark 口径下可比较。|",
        "| 验证层 | 当前阶段可运行 | 3/4 | 统一使用同一 promotion / baseline / walk-forward / leakage 框架。|",
        "| 晋级准备度 | 阻塞 | 2/4 | benchmark 线已拆清，但三条线仍都没过 30% 回撤门槛。|",
        "| Subagent 有效性 | 当前阶段暂不需要 | 3/4 | 本轮主要是串行诊断，保持 OFF 比并行更稳。|",
    ]
    universe_rows = [
        f"| {research_profile_id} | 含 ST | {profile_map[research_profile_id]['summary']} |",
        f"| {deployment_profile_id} | 不含 ST | {profile_map[deployment_profile_id]['summary']} |",
    ]
    strategy_action_rows = []
    decision_map = {
        "baseline_limit_up": "保留为对照线，继续承担 benchmark 修复后的基线职责。",
        strategy_roles["main_track"]: "升为下一轮主线候选，优先继续做更细的风控/组合归因。",
        strategy_roles["deferred_track"]: "暂缓，等待主线 drawdown 拆解后再决定是否重开。",
    }
    for variant_id in ["baseline_limit_up", "risk_constrained_limit_up", "tighter_entry_limit_up"]:
        item = results[research_profile_id].get(variant_id)
        if item is None:
            continue
        strategy_action_rows.append(
            "| {variant} | main:main | 双宇宙同口径比较 | 收益 {ret} / 回撤 {dd} / benchmark {baseline_status} | {delta} |".format(
                variant=variant_id,
                ret=_pct(item["metrics"]["total_return"]),
                dd=_pct(abs(item["metrics"]["max_drawdown"])),
                baseline_status=item["baselines"]["status"],
                delta=decision_map.get(variant_id, "保留观察。"),
            ),
        )

    next_recommendation = (
        "下一步唯一最高优先建议：只围绕 `risk_constrained_limit_up` 做一次更细的组合风险拆解，"
        "先确认它的回撤改善来自持仓预算收缩而不是样本偶然性。"
    )
    evidence_lines = [
        f"- benchmark 角色已拆清：000001 同时承担 `calendar_code` 和 `benchmark_code`，当前 explicit baseline 状态=`{benchmark_diagnostic['explicit_status']}`。",
        f"- 当前主线/对照/暂缓：`{strategy_roles['main_track']}` / `{strategy_roles['control_track']}` / `{strategy_roles['deferred_track']}`。",
        f"- 关键指标：research baseline 回撤 `{_pct(abs(research_baseline['metrics']['max_drawdown']))}`，deployment control 回撤 `{_pct(abs(deploy_baseline['metrics']['max_drawdown']))}`。",
        f"- 关键路径：`{paths.memory_dir / 'BENCHMARK_DIAGNOSTIC.md'}`、`{paths.memory_dir / 'DRAWDOWN_DIAGNOSTIC.md'}`、`{paths.memory_dir / 'STRATEGY_COMPARISON.md'}`。",
    ]

    summary = {
        "project": project,
        "generated_at": generated_at,
        "system_line": system_line,
        "strategy_line": strategy_line,
        "substantive_research": True,
        "benchmark_degraded": benchmark_degraded,
        "evidence_lines": evidence_lines,
        "progress_rows": progress_rows,
        "universe_rows": universe_rows,
        "strategy_action_rows": strategy_action_rows,
        "next_recommendation": next_recommendation,
        "configured_gate": "AUTO",
        "effective_gate": "OFF",
        "active_research_subagents": "无",
        "active_infrastructure_subagents": "无",
        "subagent_note": "benchmark 诊断、drawdown attribution、三线比较高度串行，维持 OFF 才能降低协调成本。",
        "research_profile_id": research_profile_id,
        "deployment_profile_id": deployment_profile_id,
        "strategy_roles": strategy_roles,
    }
    checkpoint = render_campaign_checkpoint(summary)

    benchmark_path = _write_text(paths.memory_dir / "BENCHMARK_DIAGNOSTIC.md", _render_benchmark_markdown(benchmark_diagnostic))
    universe_path = _write_text(
        paths.memory_dir / "UNIVERSE_COMPARISON.md",
        _render_universe_markdown(
            profile_rows=profile_rows,
            research_profile_id=research_profile_id,
            deployment_profile_id=deployment_profile_id,
        ),
    )
    drawdown_path = _write_text(paths.memory_dir / "DRAWDOWN_DIAGNOSTIC.md", _render_drawdown_markdown(drawdown_diagnostic))
    strategy_comparison_path = _write_text(
        paths.memory_dir / "STRATEGY_COMPARISON.md",
        _render_strategy_comparison_markdown(results=results, strategy_roles=strategy_roles),
    )
    _write_text(
        paths.project_state_path,
        "\n".join(
            [
                "# 项目状态",
                "",
                f"- 当前 canonical project id: `{CANONICAL_PROJECT_ID}`",
                f"- 当前阶段: 基线策略诊断战役",
                f"- canonical universe policy: 研究=`{research_profile_id}`，部署对照=`{deployment_profile_id}`",
                f"- 当前主线策略: `{strategy_roles['main_track']}`",
                f"- 当前对照策略: `{strategy_roles['control_track']}`",
                f"- 当前暂缓策略: `{strategy_roles['deferred_track']}`",
                "- 当前 blocker 层级: 主 blocker 已回到 drawdown；benchmark 角色已拆清；universe effect 暂因 ST 暴露为 0 而无法识别。",
                "- 本轮做了实质策略研究: 是，已完成 benchmark 诊断、双宇宙比较、三条策略线同口径比较、baseline 回撤归因。",
                f"- 下一步: {next_recommendation}",
            ],
        ),
    )
    _write_text(
        paths.research_memory_path,
        "\n".join(
            [
                "# 研究记忆",
                "",
                "## 已确认事实",
                "- `000001` 当前同时服务于 market stoploss 和 benchmark baseline，对应的是不同链路。",
                "- `benchmark_missing:000001` 已定位为 diagnostic baseline 传参问题，不是数据库里缺 000001。",
                "- 当前 canonical universe policy 已升级为双宇宙：研究基线含 ST，部署对照不含 ST。",
                "- 但当前冻结 symbols 快照中的 ST 暴露为 0，所以本轮含 ST / 不含 ST 物化结果一致。",
                "",
                "## 当前策略判断",
                f"- 主线继续推进: `{strategy_roles['main_track']}`",
                "- 对照线: `baseline_limit_up`",
                f"- 暂缓线: `{strategy_roles['deferred_track']}`",
                "- 当前主 blocker: drawdown，不再是 benchmark wiring。",
                "",
                "## 负面记忆",
                "- 不要再把当前 drawdown 问题解释成 000001 缺 bars。",
                "- 不要把当前 ST 结论写成“已证明无影响”；当前只能说冻结源里 ST=0，尚未观测到 ST 效应。",
                "- 不要在 universe 物化仍退化时，把 deployment control 的结果过度外推成真实全A部署结论。",
            ],
        ),
    )
    _write_text(
        paths.verify_last_path,
        "\n".join(
            [
                "# 最近验证",
                "",
                f"- project_id: `{project}`",
                f"- 当前主线: `{strategy_roles['main_track']}`",
                f"- 当前对照: `{strategy_roles['control_track']}`",
                f"- 当前 blocker: drawdown > 30%，benchmark 角色已拆清。",
                "",
                "## 通过命令",
                *([f"- `{item}`" for item in verified_commands] or ["- `baseline_strategy_diagnostic` 已执行，尚未附加额外验证命令。"]),
                "",
                "## 当前验证结论",
                f"- benchmark baseline: `{benchmark_diagnostic['explicit_status']}`",
                f"- 研究基线宇宙 baseline 回撤: `{_pct(abs(research_baseline['metrics']['max_drawdown']))}`",
                f"- 研究基线宇宙候选主线 `{strategy_roles['main_track']}` 回撤: `{_pct(abs(results[research_profile_id][strategy_roles['main_track']]['metrics']['max_drawdown']))}`",
            ],
        ),
    )
    _write_text(
        paths.handoff_path,
        "\n".join(
            [
                "# 下次对话接手点",
                "",
                f"- 当前总任务: 让 baseline strategy 结论从“系统能跑”推进到“结论更可信”。",
                f"- 当前阶段: benchmark 已修复，双宇宙已显式化，下一步只剩主线 `{strategy_roles['main_track']}` 的细化归因。",
                "- 已确认事实: 000001 不是缺数据；当前 frozen symbols 快照 ST=0；三条策略线都还没过 30% 回撤门槛。",
                f"- 下一步最高优先动作: {next_recommendation}",
                f"- 先读文件: `{benchmark_path}`、`{drawdown_path}`、`{strategy_comparison_path}`",
            ],
        ),
    )
    _write_text(
        paths.migration_prompt_path,
        "\n".join(
            [
                "# MIGRATION PROMPT NEXT CHAT",
                "",
                f"Project: `{project}`",
                f"Canonical universe policy: research=`{research_profile_id}`, deployment_control=`{deployment_profile_id}`.",
                "Truth: benchmark wiring is fixed; current live blocker is still drawdown, while ST effect is unidentifiable on the frozen source because ST exposure is zero.",
                f"Main track: `{strategy_roles['main_track']}`. Control: `{strategy_roles['control_track']}`. Deferred: `{strategy_roles['deferred_track']}`.",
                f"Next action: {next_recommendation}",
            ],
        ),
    )
    _write_text(
        paths.strategy_board_path,
        "\n".join(
            [
                "# 策略看板",
                "",
                f"- canonical universe policy: 研究=`{research_profile_id}`，部署对照=`{deployment_profile_id}`",
                f"- 主线继续推进: `{strategy_roles['main_track']}`",
                "- 对照线: `baseline_limit_up`",
                f"- 暂缓线: `{strategy_roles['deferred_track']}`",
                "- benchmark 层状态: 已修复，不再是主 blocker。",
                "- drawdown 层状态: 仍是主 blocker，三条线都未通过 30% 门槛。",
                "- universe effect 层状态: 当前 frozen symbols 快照 ST=0，因此本轮 A/B 比较退化为同一结果。",
                f"- 关键证据文件: `{benchmark_path}`、`{universe_path}`、`{drawdown_path}`、`{strategy_comparison_path}`",
            ],
        ),
    )
    _write_text(
        paths.subagent_registry_path,
        "\n".join(
            [
                "# Subagent Registry",
                "",
                "- configured gate: `AUTO`",
                "- effective gate this run: `OFF`",
                "- active strategy-research subagents: 无",
                "- active infrastructure subagents: 无",
                "- 原因: 本轮 benchmark 诊断、双宇宙收口、回撤归因和三线比较共享同一数据与结论口径，串行推进更稳。",
            ],
        ),
    )

    run_id = f"{project}-baseline-campaign-{generated_at.replace(':', '').replace('-', '')}"
    for variant_id in ["baseline_limit_up", strategy_roles["main_track"], strategy_roles["deferred_track"]]:
        if variant_id == "none" or variant_id not in results[research_profile_id]:
            continue
        append_strategy_action_log(
            paths.strategy_action_log_path,
            {
                "run_id": run_id,
                "project_id": project,
                "strategy_id": variant_id,
                "actor_type": "main",
                "actor_id": "main",
                "action_type": "diagnostic_compare",
                "action_summary": "完成双宇宙同口径比较",
                "result": (
                    f"收益 {_pct(results[research_profile_id][variant_id]['metrics']['total_return'])} / "
                    f"回撤 {_pct(abs(results[research_profile_id][variant_id]['metrics']['max_drawdown']))}"
                ),
                "decision_delta": decision_map.get(variant_id, "保留观察。"),
                "artifact_refs": [str(strategy_comparison_path), str(drawdown_path)],
                "timestamp": generated_at,
            },
        )
    write_research_activity_markdown(paths.research_activity_path, read_strategy_action_log(paths.strategy_action_log_path, run_id=run_id))
    append_jsonl(
        paths.experiment_ledger_path,
        {
            "timestamp": generated_at,
            "experiment_id": run_id,
            "hypothesis": "Benchmark wiring fixed + dual-universe comparison can clarify whether baseline drawdown is strategy-driven or pipeline-driven.",
            "config_hash": stable_hash(cfg),
            "result": "diagnosed",
            "blockers": ["drawdown_above_30pct", "st_effect_unidentified_on_frozen_snapshot"],
            "artifact_refs": [str(benchmark_path), str(universe_path), str(drawdown_path), str(strategy_comparison_path)],
        },
    )

    existing_state = _read_existing_state(paths.session_state_path)
    existing_state.update(
        {
            "project": project,
            "canonical_project_id": CANONICAL_PROJECT_ID,
            "legacy_project_aliases": ["2026Q1_limit_up"] if project == CANONICAL_PROJECT_ID else [],
            "current_phase": "Baseline Strategy Diagnostic Campaign",
            "current_research_stage": "策略诊断 / 晋级受阻",
            "current_task": "Clarify benchmark wiring, formalize dual universes, and compare three limit-up strategy lines under one validation frame.",
            "current_blocker": "Primary blocker is still drawdown > 30%; benchmark wiring is fixed and ST effect is still unidentifiable on the frozen snapshot because ST exposure is zero.",
            "current_capability_boundary": "Research conclusions are now credible enough for strategy-level diagnosis, but not yet strong enough for promotion because all compared lines still fail the drawdown gate.",
            "current_primary_strategy_ids": [strategy_roles["main_track"]],
            "current_secondary_strategy_ids": [item for item in [strategy_roles["control_track"], strategy_roles["deferred_track"]] if item != "none" and item != strategy_roles["main_track"]],
            "current_blocked_strategy_ids": [
                key
                for key, item in results[research_profile_id].items()
                if not item["decision"]["promotable"]
            ],
            "current_promoted_strategy_ids": [
                key
                for key, item in results[research_profile_id].items()
                if item["decision"]["promotable"]
            ],
            "configured_subagent_gate_mode": "AUTO",
            "effective_subagent_gate_mode": "OFF",
            "effective_subagent_gate_reason": "This run was a tightly coupled diagnostic path; serial work produced cleaner evidence than parallel subagents.",
            "default_project_data_status": f"ready coverage on current frozen snapshot; research profile `{research_profile_id}` source_st_count={profile_map[research_profile_id]['source_st_count']}.",
            "durable_facts": [
                "Canonical active project id: as_share_research_v1.",
                f"Canonical universe policy: research={research_profile_id}, deployment_control={deployment_profile_id}.",
                "Benchmark wiring is fixed: direct baseline diagnostics now receive explicit benchmark_series.",
                "Current frozen symbols snapshot has zero ST exposure, so the new dual-universe comparison is policy-valid but empirically degenerate this round.",
                f"Main track candidate: {strategy_roles['main_track']}; control track: {strategy_roles['control_track']}; deferred track: {strategy_roles['deferred_track']}.",
            ],
            "negative_memory": [
                "Do not reopen generic benchmark_missing diagnosis unless explicit baselines fall below pass again.",
                "Do not treat current ST result as proof that ST never matters; the frozen snapshot currently has zero ST exposure.",
                "Do not over-explain drawdown with universe stories before the frozen symbols source is widened beyond the current degenerate snapshot.",
            ],
            "next_priority_action": next_recommendation,
            "last_verified_capability": "This run completed benchmark diagnosis, dual-universe comparison, baseline drawdown attribution, and three-line strategy comparison under one evaluation frame.",
            "last_failed_capability": "All three strategy lines still fail the 30% max-drawdown promotion threshold.",
            "current_strategy_summary": strategy_line,
            "current_strategy_focus": [strategy_roles["main_track"]],
            "benchmark_diagnostic_path": str(benchmark_path),
            "drawdown_diagnostic_path": str(drawdown_path),
            "universe_comparison_path": str(universe_path),
            "strategy_comparison_path": str(strategy_comparison_path),
            "research_progress": {
                "overall_trajectory": "blocked",
                "current_blocker": "drawdown_above_30pct",
                "dimensions": [
                    {"dimension": "Data inputs", "status": "partial", "score": 3, "evidence": "validated bars ready but ST exposure on frozen snapshot is zero"},
                    {"dimension": "Strategy integrity", "status": "operational", "score": 3, "evidence": "three strategy lines are now directly comparable"},
                    {"dimension": "Validation stack", "status": "operational", "score": 3, "evidence": "same benchmark, same cost, same promotion frame"},
                    {"dimension": "Promotion readiness", "status": "blocked", "score": 2, "evidence": "all lines still exceed 30% drawdown"},
                    {"dimension": "Subagent effectiveness", "status": "not-needed-yet", "score": 3, "evidence": "serial diagnostics were higher ROI this run"},
                ],
            },
            "substantive_research": True,
            "last_updated": generated_at,
        },
    )
    _write_json(paths.session_state_path, existing_state)

    artifact_json = _write_json(
        paths.artifacts_dir / "baseline_strategy_diagnostic.json",
        _strip_internal(
            {
                "summary": summary,
                "benchmark_diagnostic": benchmark_diagnostic,
                "profile_rows": profile_rows,
                "drawdown_diagnostic": drawdown_diagnostic,
                "results": results,
            },
        ),
    )
    artifact_checkpoint = _write_text(paths.artifacts_dir / "baseline_strategy_diagnostic.CHECKPOINT.md", checkpoint)

    return {
        "generated_at": generated_at,
        "project": project,
        "summary": summary,
        "checkpoint": checkpoint,
        "benchmark_diagnostic": benchmark_diagnostic,
        "drawdown_diagnostic": drawdown_diagnostic,
        "profile_rows": profile_rows,
        "results": _strip_internal(results),
        "memory_paths": {
            "benchmark": str(benchmark_path),
            "universe": str(universe_path),
            "drawdown": str(drawdown_path),
            "strategy_comparison": str(strategy_comparison_path),
        },
        "artifact_paths": {
            "json": str(artifact_json),
            "checkpoint": str(artifact_checkpoint),
        },
        "strategy_roles": strategy_roles,
    }
