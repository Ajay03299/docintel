from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from app.schemas.validation import Severity, ValidationResult


class DuplicateLookup(Protocol):
    """Port for cross-document duplicate detection. Implemented against the DB
    in production, faked in tests — rules never touch a Session directly."""

    def find_duplicates(
        self,
        *,
        vendor_name: str | None,
        invoice_number: str | None,
        total: float | None,
        exclude_document_id: str | None,
    ) -> list[str]: ...


class VendorDirectory(Protocol):
    """Port for 'is this a vendor we do business with?'."""

    def is_known(self, vendor_name: str) -> bool: ...


@dataclass
class ValidationContext:
    """Everything a rule may need. Rules are pure functions of this context:
    no DB sessions, no clock reads, no config file access — all injected, so
    every rule is deterministic and unit-testable."""

    data: dict[str, Any]
    source_text: str = ""
    document_id: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    duplicate_lookup: DuplicateLookup | None = None
    vendor_directory: VendorDirectory | None = None
    now: datetime | None = None  # injectable clock -> date rules are deterministic


class ValidationRule(ABC):
    """Base for every rule.

    Contract: evaluate() must NEVER raise for bad data — return SKIPPED instead.
    The service isolates exceptions anyway, but a rule that handles its own
    missing data gives a far better reason string.
    """

    rule_id: str = ""
    description: str = ""

    # Can a better extraction of THIS SAME document plausibly make this pass?
    # False = the failure is a fact about the document or about other documents
    # (future date, duplicate, unknown vendor) — re-running the model is waste.
    # Default False: a new rule must opt IN to costing us a retry.
    retryable: bool = False

    @abstractmethod
    def evaluate(self, ctx: ValidationContext) -> ValidationResult: ...

    # --- result helpers: keep 17 rule implementations free of boilerplate ---

    def _result(
        self,
        severity: Severity,
        reason: str,
        *,
        confidence: float = 1.0,
        suggested_fix: str | None = None,
        fields: list[str] | None = None,
    ) -> ValidationResult:
        return ValidationResult(
            rule_id=self.rule_id,
            severity=severity,
            reason=reason,
            confidence=confidence,
            suggested_fix=suggested_fix,
            fields=fields or [],
        )

    def ok(self, reason: str, **kw: Any) -> ValidationResult:
        return self._result(Severity.PASS, reason, **kw)

    def warn(self, reason: str, **kw: Any) -> ValidationResult:
        return self._result(Severity.WARNING, reason, **kw)

    def fail(self, reason: str, **kw: Any) -> ValidationResult:
        return self._result(Severity.FAIL, reason, **kw)

    def skip(self, reason: str, **kw: Any) -> ValidationResult:
        return self._result(Severity.SKIPPED, reason, **kw)
