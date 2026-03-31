from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEMORY = ROOT / "memory" / "projects" / "as_share_research_v1"


def test_universe_policy_records_canonical_rules() -> None:
    text = (MEMORY / "UNIVERSE_POLICY.md").read_text(encoding="utf-8")

    assert "cn_a_mainboard_all_v1" in text
    assert "Inclusion Rules" in text
    assert "Exclusion Rules" in text
    assert "ST Handling" in text
    assert "exchange" in text
    assert "security_type" in text
    assert "ST" in text
    assert "ETF" in text
    assert "LOF" in text


def test_universe_audit_and_legacy_note_match_reset_story() -> None:
    audit = (MEMORY / "UNIVERSE_AUDIT.md").read_text(encoding="utf-8")
    legacy = (MEMORY / "LEGACY_UNIVERSE_NOTE.md").read_text(encoding="utf-8")

    assert "3193" in audit
    assert "1703" in audit
    assert "1490" in audit
    assert "129" in audit
    assert "为什么它比旧 715 标的池更接近目标研究对象" in audit
    assert "not active truth" in legacy
    assert "legacy comparison only" in legacy


def test_strategy_board_and_baseline_reset_note_reflect_current_blocker() -> None:
    board = (MEMORY / "STRATEGY_BOARD.md").read_text(encoding="utf-8")
    reset = (MEMORY / "BASELINE_RESET_NOTE.md").read_text(encoding="utf-8")

    assert "baseline_limit_up" in board
    assert "risk_constrained_limit_up" in board
    assert "risk_constrained_limit_up" in reset
    assert "tighter_entry_limit_up" in reset
    assert "baseline_validation_ready" in reset
    assert "Rank dataframe is empty" in reset


def test_session_state_records_current_canonical_truth() -> None:
    session = json.loads((MEMORY / "SESSION_STATE.json").read_text(encoding="utf-8"))

    assert session["canonical_universe_id"] == "cn_a_mainboard_all_v1"
    assert session["baseline_status"] == "baseline_validation_ready"
    assert session["readiness"]["stage"] == "validation-ready"
    assert session["readiness"]["ready"] is True
    assert session["effective_subagent_gate_mode"] == "OFF"
