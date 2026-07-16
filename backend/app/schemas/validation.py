from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    SKIPPED = "skipped"  # rule could not run (missing data or unavailable lookup)


class ValidationResult(BaseModel):
    """Outcome of one rule against one document."""

    rule_id: str
    severity: Severity
    reason: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    suggested_fix: str | None = None
    fields: list[str] = Field(default_factory=list)  # which fields the rule implicates


class ValidationReport(BaseModel):
    overall: Severity
    results: list[ValidationResult]
    counts: dict[str, int] = Field(default_factory=dict)

    @property
    def failures(self) -> list[ValidationResult]:
        return [r for r in self.results if r.severity is Severity.FAIL]
