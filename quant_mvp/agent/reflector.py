from __future__ import annotations

from .schemas import ReflectionRecord


def build_reflection(payload: dict) -> ReflectionRecord:
    return ReflectionRecord(
        summary=str(payload.get("summary", "")),
        next_hypotheses=list(payload.get("next_hypotheses", [])),
        lessons=list(payload.get("lessons", [])),
    )
