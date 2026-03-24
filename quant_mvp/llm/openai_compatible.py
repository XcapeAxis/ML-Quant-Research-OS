from __future__ import annotations

import os
from typing import Any

import httpx

from .base import LLMBackend


class OpenAICompatibleLLM(LLMBackend):
    backend_name = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = base_url or os.getenv("OPENAI_COMPAT_BASE_URL") or "https://api.openai.com/v1"
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL") or "gpt-4.1-mini"

    def _request(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for the openai_compatible backend")
        response = httpx.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "Return concise JSON only."},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=60.0,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"]

    def generate_hypotheses(self, *, project: str, context: str) -> list[str]:
        text = self._request(
            f"Project: {project}\nContext:\n{context}\nReturn JSON array of two research hypotheses.",
        )
        return [item.strip() for item in text.strip("[] \n").split(",") if item.strip()]

    def plan_experiment(self, *, project: str, hypotheses: list[str], context: str) -> dict[str, Any]:
        text = self._request(
            f"Project: {project}\nHypotheses: {hypotheses}\nContext:\n{context}\nReturn a JSON object describing a guarded experiment plan.",
        )
        return {"raw_response": text, "mode": "openai_compatible"}

    def reflect(self, *, project: str, evaluation: dict[str, Any], context: str) -> dict[str, Any]:
        text = self._request(
            f"Project: {project}\nEvaluation: {evaluation}\nContext:\n{context}\nReturn a JSON object with reflection summary and next hypotheses.",
        )
        return {"raw_response": text, "mode": "openai_compatible"}
