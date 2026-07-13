import time

import httpx

from app.engines.understanding.providers.base import LLMProvider
from app.schemas.llm import LLMResponse


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float = 120.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def complete(self, *, system: str, prompt: str, json_schema: dict | None = None) -> LLMResponse:
        payload: dict = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "options": {"temperature": 0},  # deterministic extraction
        }
        if json_schema is not None:
            payload["format"] = json_schema  # Ollama constrains output to this schema

        start = time.perf_counter()
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
        elapsed = (time.perf_counter() - start) * 1000
        body = resp.json()

        return LLMResponse(
            text=body["message"]["content"],
            model=self._model,
            prompt_tokens=body.get("prompt_eval_count"),
            completion_tokens=body.get("eval_count"),
            latency_ms=elapsed,
        )