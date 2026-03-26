from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_response_contract_exists_and_is_referenced() -> None:
    contract_path = ROOT / "docs" / "RESPONSE_CONTRACT.md"
    agents_path = ROOT / "AGENTS.md"
    contract = contract_path.read_text(encoding="utf-8")

    assert contract_path.exists()
    assert "CHECKPOINT" in contract
    assert "Evidence" in contract
    assert "Research progress" in contract
    assert "Strategy actions this run" in contract
    assert "Next recommendation" in contract
    assert "Subagent status" in contract
    assert "系统推进" in contract
    assert "策略推进" in contract
    assert "Chinese" in contract or "中文" in contract
    assert "docs/RESPONSE_CONTRACT.md" in agents_path.read_text(encoding="utf-8")
    assert "subagents" in agents_path.read_text(encoding="utf-8").lower()
