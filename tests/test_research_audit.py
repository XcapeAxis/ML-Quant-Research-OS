from __future__ import annotations

from pathlib import Path

from quant_mvp.research_audit import run_research_audit


ROOT = Path(__file__).resolve().parents[1]


def test_research_audit_preserves_existing_decision_log_entries(synthetic_project) -> None:
    decision_log_path = ROOT / "docs" / "DECISION_LOG.md"
    extra_line = "- Auto-refreeze the default project from 3063 to 715 symbols after the Stage 0A coverage-gap ledger showed the original frozen universe was not conservatively recoverable."
    decision_log_path.write_text(
        "# Decision Log\n\n## 2026-03-25\n"
        "- Add a research-readiness gate ahead of promotion so partial coverage is classified as pilot recovery rather than strategy evidence.\n"
        f"{extra_line}\n",
        encoding="utf-8",
    )

    run_research_audit(
        synthetic_project["project"],
        repo_root=ROOT,
        config_path=synthetic_project["config_path"],
    )

    text = decision_log_path.read_text(encoding="utf-8")
    assert extra_line in text
    assert "## 2026-03-24" in text
    assert "## 2026-03-25" in text
