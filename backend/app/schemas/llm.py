from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    """Raw envelope around a single LLM call. Provider-agnostic."""
    text: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: float | None = None


class FieldConfidence(BaseModel):
    """Per-field confidence + provenance for downstream aggregation & review."""
    value: object | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    reason: str | None = None