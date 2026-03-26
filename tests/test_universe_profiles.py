from __future__ import annotations

import json

import pandas as pd

from quant_mvp.universe_profiles import load_universe_profile_definition, materialize_universe_profile


def test_universe_profile_definitions_exist_and_are_distinct() -> None:
    incl = load_universe_profile_definition("full_a_mainboard_incl_st")
    ex = load_universe_profile_definition("full_a_mainboard_ex_st")

    assert incl.profile_id == "full_a_mainboard_incl_st"
    assert ex.profile_id == "full_a_mainboard_ex_st"
    assert incl.include_st is True
    assert ex.include_st is False


def test_materialize_universe_profile_respects_st_policy(limit_up_project) -> None:
    ctx = limit_up_project
    symbols = pd.DataFrame(
        [
            {"code": "000001", "name": "平安银行", "is_st": False, "board": "mainboard"},
            {"code": "000002", "name": "ST样本", "is_st": True, "board": "mainboard"},
            {"code": "000003", "name": "万科A", "is_st": False, "board": "mainboard"},
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
    ctx["config_path"].write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    incl = materialize_universe_profile(ctx["project"], "full_a_mainboard_incl_st", config_path=ctx["config_path"])
    ex = materialize_universe_profile(ctx["project"], "full_a_mainboard_ex_st", config_path=ctx["config_path"])

    assert incl.included_count == 6
    assert incl.included_st_count == 1
    assert ex.included_count == 5
    assert ex.included_st_count == 0
    assert "000002" in incl.codes
    assert "000002" not in ex.codes
