from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_response_contract_exists_and_is_referenced() -> None:
    contract_path = ROOT / "docs" / "RESPONSE_CONTRACT.md"
    agents_path = ROOT / "AGENTS.md"

    assert contract_path.exists()
    assert "CHECKPOINT" in contract_path.read_text(encoding="utf-8")
    assert "docs/RESPONSE_CONTRACT.md" in agents_path.read_text(encoding="utf-8")
