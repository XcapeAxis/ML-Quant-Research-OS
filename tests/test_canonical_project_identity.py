from __future__ import annotations

import json
from pathlib import Path

from quant_mvp.project import resolve_project_paths
from quant_mvp.project_identity import CANONICAL_PROJECT_ID, LEGACY_PROJECT_ALIASES, canonical_project_id


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_MEMORY_FILES = [
    "PROJECT_STATE.md",
    "RESEARCH_MEMORY.md",
    "VERIFY_LAST.md",
    "HANDOFF_NEXT_CHAT.md",
    "MIGRATION_PROMPT_NEXT_CHAT.md",
    "SESSION_STATE.json",
    "STRATEGY_BOARD.md",
    "SUBAGENT_REGISTRY.md",
    "RESEARCH_PROGRESS.md",
    "EXECUTION_QUEUE.md",
    "HYPOTHESIS_QUEUE.md",
]
FORBIDDEN_ACTIVE_PATTERNS = [
    '"project": "2026Q1_limit_up"',
    "mission-2026Q1_limit_up",
    "/projects/2026Q1_limit_up/",
    "\\projects\\2026Q1_limit_up\\",
    "data/projects/2026Q1_limit_up",
    "artifacts/projects/2026Q1_limit_up",
    "full_a_mainboard_incl_st",
    "full_a_mainboard_ex_st",
    "715-symbol",
    "715 symbol",
]


def test_legacy_alias_resolves_to_canonical_project() -> None:
    paths = resolve_project_paths("2026Q1_limit_up")

    assert CANONICAL_PROJECT_ID == "crypto_okx_research_v1"
    assert paths.project == "as_share_research_v1"
    assert canonical_project_id("2026Q1_limit_up") == "as_share_research_v1"
    assert LEGACY_PROJECT_ALIASES["2026Q1_limit_up"] == "as_share_research_v1"


def test_active_canonical_memory_surfaces_do_not_use_legacy_as_default() -> None:
    base = ROOT / "memory" / "projects" / CANONICAL_PROJECT_ID

    for name in ACTIVE_MEMORY_FILES:
        path = base / name
        assert path.exists(), f"missing active tracked-memory file: {path}"
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_ACTIVE_PATTERNS:
            assert pattern not in text, f"{name} still leaks legacy active reference: {pattern}"


def test_active_session_state_keeps_one_coherent_blocker_story() -> None:
    session_path = ROOT / "memory" / "projects" / CANONICAL_PROJECT_ID / "SESSION_STATE.json"
    session = json.loads(session_path.read_text(encoding="utf-8"))
    truth_text = json.dumps(session, ensure_ascii=False)

    assert session["project"] == CANONICAL_PROJECT_ID
    assert session["canonical_project_id"] == CANONICAL_PROJECT_ID
    assert session["canonical_universe_id"] == "okx_crypto_linear_swap_v1"
    assert session["legacy_project_aliases"] == []
    assert session["configured_subagent_gate_mode"] in {"AUTO", "OFF", "FORCE"}
    assert session["effective_subagent_gate_mode"] in {"OFF", "AUTO", "FORCE"}
    assert isinstance(session.get("current_research_stage"), str)
    assert session["current_research_stage"].strip()
    assert isinstance(session.get("canonical_truth_summary"), str)
    assert session["canonical_truth_summary"].strip()
    assert "okx_crypto_linear_swap_v1" in truth_text
    assert "phase0_prerequisites_blocked" in truth_text
    assert "usable raw bars" in truth_text
    assert "715" not in truth_text
    assert "full_a_mainboard_incl_st" not in truth_text
    assert "full_a_mainboard_ex_st" not in truth_text
