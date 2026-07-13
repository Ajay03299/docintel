import json

import structlog
from pydantic import BaseModel, ValidationError

from app.engines.understanding.providers.base import LLMProvider

log = structlog.get_logger()


class StructuredExtractionResult(BaseModel):
    data: dict
    raw_text: str
    model: str
    parse_attempts: int
    parse_error: str | None = None
    latency_ms: float | None = None


def _strip_json_fences(text: str) -> str:
    """Small models often wrap JSON in ```json ... ``` despite instructions."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if "```" in t[3:] else t[3:]
        if t.startswith("json"):
            t = t[4:]
    return t.strip().strip("`").strip()


class StructuredExtractor:
    """Turns document text into schema-valid structured data via an LLMProvider.

    Failure policy (the design decision):
      - Unparseable output  -> bounded retry with a firmer instruction.
      - Parseable but schema-invalid -> keep what validates, record the error,
        never raise. Downstream review handles low-quality extractions."""

    def __init__(self, provider: LLMProvider, max_retries: int = 1) -> None:
        self._provider = provider
        self._max_retries = max_retries

    def extract(
        self, *, document_text: str, system_prompt: str, user_prompt: str,
        schema_model: type[BaseModel],
    ) -> StructuredExtractionResult:
        json_schema = schema_model.model_json_schema()
        last_error: str | None = None
        raw = ""
        latency = None

        for attempt in range(1, self._max_retries + 2):  # 1 initial + N retries
            firmer = user_prompt if attempt == 1 else (
                user_prompt + "\n\nYour previous response was not valid JSON. "
                "Return ONLY a valid JSON object, no prose, no code fences."
            )
            resp = self._provider.complete(
                system=system_prompt, prompt=firmer, json_schema=json_schema
            )
            raw, latency = resp.text, resp.latency_ms
            cleaned = _strip_json_fences(resp.text)

            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as e:
                last_error = f"JSONDecodeError (attempt {attempt}): {e}"
                log.warning("extraction.parse_failed", attempt=attempt, error=str(e))
                continue  # → bounded retry

            # Parsed OK. Validate against schema, but keep partial data on failure.
            try:
                validated = schema_model.model_validate(parsed)
                return StructuredExtractionResult(
                    data=validated.model_dump(), raw_text=raw, model=resp.model,
                    parse_attempts=attempt, parse_error=None, latency_ms=latency,
                )
            except ValidationError as e:
                # Schema-violating: salvage valid fields, record the violation.
                last_error = f"ValidationError (attempt {attempt}): {e.error_count()} field(s)"
                log.warning("extraction.schema_invalid", attempt=attempt, errors=e.error_count())
                return StructuredExtractionResult(
                    data=parsed, raw_text=raw, model=resp.model,
                    parse_attempts=attempt, parse_error=last_error, latency_ms=latency,
                )

        # Exhausted retries without parseable JSON.
        return StructuredExtractionResult(
            data={}, raw_text=raw, model=self._provider.name,
            parse_attempts=self._max_retries + 1, parse_error=last_error, latency_ms=latency,
        )