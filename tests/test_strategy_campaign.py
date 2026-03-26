from __future__ import annotations

import json

import pandas as pd

from quant_mvp.strategy_campaign import render_campaign_checkpoint, run_baseline_strategy_diagnostic


def _prepare_campaign_fixture(limit_up_project) -> None:
    ctx = limit_up_project
    symbols = pd.DataFrame(
        [
            {"code": "000001", "name": "平安银行", "is_st": False, "board": "mainboard"},
            {"code": "000002", "name": "万科A", "is_st": False, "board": "mainboard"},
            {"code": "000003", "name": "ST样本", "is_st": True, "board": "mainboard"},
            {"code": "000004", "name": "国华网安", "is_st": False, "board": "mainboard"},
            {"code": "000005", "name": "世纪星源", "is_st": False, "board": "mainboard"},
            {"code": "000006", "name": "深振业A", "is_st": False, "board": "mainboard"},
        ],
    )
    symbols.to_csv(ctx["paths"].meta_dir / "symbols.csv", index=False, encoding="utf-8-sig")

    cfg = json.loads(ctx["config_path"].read_text(encoding="utf-8"))
    cfg["universe_policy"] = {
        "research_profile": "full_a_mainboard_incl_st",
        "deployment_profile": "full_a_mainboard_ex_st",
        "comparison_profiles": ["full_a_mainboard_incl_st", "full_a_mainboard_ex_st"],
    }
    cfg["strategy_variants"] = {
        "baseline_limit_up": {
            "title": "baseline_limit_up",
            "decision_role": "control",
            "thesis": "保留默认基线。",
            "overrides": {},
        },
        "risk_constrained_limit_up": {
            "title": "risk_constrained_limit_up",
            "decision_role": "candidate",
            "thesis": "收紧持仓预算。",
            "overrides": {"stock_num": 2, "topk": 2, "topn_max": 2},
        },
        "tighter_entry_limit_up": {
            "title": "tighter_entry_limit_up",
            "decision_role": "candidate",
            "thesis": "收紧入场阈值。",
            "overrides": {"top_pct_limit_up": 0.4, "init_pool_size": 5},
        },
    }
    ctx["config_path"].write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def test_baseline_strategy_diagnostic_writes_memory_and_checkpoint(limit_up_project) -> None:
    ctx = limit_up_project
    _prepare_campaign_fixture(ctx)

    result = run_baseline_strategy_diagnostic(ctx["project"], config_path=ctx["config_path"])

    assert "Universe comparison" in result["checkpoint"]
    assert ctx["paths"].memory_dir.joinpath("BENCHMARK_DIAGNOSTIC.md").exists()
    assert ctx["paths"].memory_dir.joinpath("STRATEGY_COMPARISON.md").exists()
    assert "000001" in ctx["paths"].memory_dir.joinpath("BENCHMARK_DIAGNOSTIC.md").read_text(encoding="utf-8")
    assert "主线继续推进" in ctx["paths"].memory_dir.joinpath("STRATEGY_COMPARISON.md").read_text(encoding="utf-8")
    assert result["memory_paths"]["benchmark"].endswith("BENCHMARK_DIAGNOSTIC.md")
    assert result["memory_paths"]["strategy_comparison"].endswith("STRATEGY_COMPARISON.md")


def test_render_campaign_checkpoint_handles_degraded_benchmark_and_no_research() -> None:
    checkpoint = render_campaign_checkpoint(
        {
            "system_line": "已刷新诊断产物。",
            "strategy_line": "默认策略线。",
            "substantive_research": False,
            "no_research_reason": "本轮未进行实质策略研究，因为 benchmark 仍未拆清。",
            "benchmark_degraded": True,
            "evidence_lines": ["- key command / metric / path evidence: benchmark_missing:000001"],
            "progress_rows": ["| 数据输入 | 阻塞 | 1/4 | benchmark 仍缺失。|"],
            "universe_rows": ["| full_a_mainboard_incl_st | 含 ST | benchmark 未拆清，结论降级。|"],
            "strategy_action_rows": ["| 本轮无实质策略研究 | main:main | 等待 benchmark 修复 | 未新增策略结论 | 无变化 |"],
            "next_recommendation": "先修 benchmark。",
            "configured_gate": "AUTO",
            "effective_gate": "OFF",
            "active_research_subagents": "无",
            "active_infrastructure_subagents": "无",
            "subagent_note": "单路径问题，继续 OFF。",
        },
    )

    assert "Universe comparison" in checkpoint
    assert "benchmark 状态仍降级" in checkpoint
    assert "本轮未进行实质策略研究，因为 benchmark 仍未拆清。" in checkpoint
