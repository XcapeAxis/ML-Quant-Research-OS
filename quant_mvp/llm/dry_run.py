from __future__ import annotations

from typing import Any

from .base import LLMBackend


class DryRunLLM(LLMBackend):
    backend_name = "dry_run"

    def generate_hypotheses(self, *, project: str, context: str) -> list[str]:
        del context
        return [
            f"{project}: revalidate spec parity before any new alpha claim",
            f"{project}: compare the audited strategy against baseline and cost stress before promotion",
        ]

    def plan_experiment(self, *, project: str, hypotheses: list[str], context: str) -> dict[str, Any]:
        del context
        primary = hypotheses[0] if hypotheses else f"{project}: no hypothesis supplied"
        return {
            "mode": "dry_run",
            "primary_hypothesis": primary,
            "steps": [
                "research_audit",
                "agent_memory_sync",
                "promote_candidate",
            ],
            "success_criteria": [
                "Audit findings are written to disk",
                "Memory files are updated",
                "Promotion decision is recorded without bypassing gates",
            ],
        }

    def reflect(self, *, project: str, evaluation: dict[str, Any], context: str) -> dict[str, Any]:
        del context
        next_hypothesis = (
            f"{project}: investigate the highest-severity failed gate before running a live experiment"
            if not evaluation.get("passed", False)
            else f"{project}: expand the dry-run plan into a real guarded experiment"
        )
        return {
            "summary": evaluation.get("summary", "dry-run evaluation complete"),
            "next_hypotheses": [next_hypothesis],
            "lessons": [
                "Dry-run cycles should still produce append-only memory artifacts.",
                "Promotion gates remain mandatory even when no live LLM backend is configured.",
            ],
        }
