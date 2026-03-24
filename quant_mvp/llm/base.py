from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMBackend(ABC):
    backend_name: str

    @abstractmethod
    def generate_hypotheses(self, *, project: str, context: str) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def plan_experiment(self, *, project: str, hypotheses: list[str], context: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def reflect(self, *, project: str, evaluation: dict[str, Any], context: str) -> dict[str, Any]:
        raise NotImplementedError
