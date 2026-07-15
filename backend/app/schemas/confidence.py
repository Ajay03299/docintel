from typing import Any

from pydantic import BaseModel, Field


class FieldScore(BaseModel):
    """Confidence for one extracted field, with the evidence that produced it."""
    field: str
    value: Any = None
    confidence: float = Field(ge=0.0, le=1.0)
    signals: list[str] = Field(default_factory=list)  # human-readable evidence trail


class ConfidenceReport(BaseModel):
    strategy: str
    overall: float = Field(ge=0.0, le=1.0)
    fields: list[FieldScore]
    critical_fields: list[str]