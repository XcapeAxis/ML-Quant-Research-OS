from __future__ import annotations

import json

import pandas as pd

from quant_mvp.universe_profiles import load_universe_profile_definition, materialize_universe_profile


def test_universe_profile_definitions_cover_canonical_and_legacy_profiles() -> None:
    canonical = load_universe_profile_definition("cn_a_mainboard_all_v1")
    incl = load_universe_profile_definition("full_a_mainboard_incl_st")
    ex = load_universe_profile_definition("full_a_mainboard_ex_st")

    assert canonical.profile_id == "cn_a_mainboard_all_v1"
    assert canonical.include_st is True
    assert canonical.allowed_exchanges == ("SSE", "SZSE")
    assert canonical.allowed_boards == ("mainboard",)
    assert canonical.allowed_security_types == ("common_stock",)
    assert canonical.allowed_share_classes == ("A",)
    assert incl.include_st is True
    assert ex.include_st is False


def test_materialize_canonical_universe_uses_security_master_metadata(limit_up_project) -> None:
    ctx = limit_up_project
    symbols = pd.DataFrame(
        [
            {
                "code": "000001",
                "name": "平安银行",
                "security_name": "平安银行",
                "exchange": "SZSE",
                "board": "mainboard",
                "security_type": "common_stock",
                "share_class": "A",
                "is_st": False,
                "st_label": "",
            },
            {
                "code": "000002",
                "name": "*ST样本",
                "security_name": "*ST样本",
                "exchange": "SZSE",
                "board": "mainboard",
                "security_type": "common_stock",
                "share_class": "A",
                "is_st": True,
                "st_label": "*ST",
            },
            {
                "code": "600000",
                "name": "浦发银行",
                "security_name": "浦发银行",
                "exchange": "SSE",
                "board": "mainboard",
                "security_type": "common_stock",
                "share_class": "A",
                "is_st": False,
                "st_label": "",
            },
            {
                "code": "300001",
                "name": "创业样本",
                "security_name": "创业样本",
                "exchange": "SZSE",
                "board": "chinext",
                "security_type": "common_stock",
                "share_class": "A",
                "is_st": False,
                "st_label": "",
            },
            {
                "code": "688001",
                "name": "科创样本",
                "security_name": "科创样本",
                "exchange": "SSE",
                "board": "star",
                "security_type": "common_stock",
                "share_class": "A",
                "is_st": False,
                "st_label": "",
            },
            {
                "code": "159001",
                "name": "ETF样本",
                "security_name": "ETF样本",
                "exchange": "SZSE",
                "board": "mainboard",
                "security_type": "etf",
                "share_class": "A",
                "is_st": False,
                "st_label": "",
            },
        ],
    )
    symbols.to_csv(ctx["paths"].meta_dir / "security_master.csv", index=False, encoding="utf-8-sig")
    symbols.to_csv(ctx["paths"].meta_dir / "symbols.csv", index=False, encoding="utf-8-sig")

    cfg = json.loads(ctx["config_path"].read_text(encoding="utf-8"))
    cfg["universe_policy"] = {
        "canonical_universe_id": "cn_a_mainboard_all_v1",
        "research_profile": "cn_a_mainboard_all_v1",
        "comparison_profiles": ["cn_a_mainboard_all_v1"],
    }
    ctx["config_path"].write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    canonical = materialize_universe_profile(ctx["project"], "cn_a_mainboard_all_v1", config_path=ctx["config_path"])
    ex = materialize_universe_profile(ctx["project"], "full_a_mainboard_ex_st", config_path=ctx["config_path"])

    assert canonical.included_count == 3
    assert canonical.included_st_count == 1
    assert canonical.codes == ["000001", "000002", "600000"]
    assert ex.codes == ["000001", "600000"]
