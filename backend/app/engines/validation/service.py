from dataclasses import replace
from typing import Any

import structlog

from app.engines.validation.base import ValidationContext, ValidationRule
from app.engines.validation.registry import get_rules
from app.schemas.validation import Severity, ValidationReport, ValidationResult

log = structlog.get_logger()

_SEVERITY_ORDER = {Severity.PASS: 0, Severity.SKIPPED: 0, Severity.WARNING: 1, Severity.FAIL: 2}


class ValidationService:
    """Runs every enabled rule and aggregates results.

    The engine knows nothing about invoices: rules come from the registry and
    their config comes from the caller's plugin.
    """

    def __init__(
        self,
        config: dict[str, Any],
        rules: dict[str, type[ValidationRule]] | None = None,
    ) -> None:
        self._config = config
        self._rules = rules if rules is not None else get_rules()

    def validate(self, ctx: ValidationContext) -> ValidationReport:
        results: list[ValidationResult] = []

        for rule_id in sorted(self._rules):
            cfg = self._config.get(rule_id, {})
            if not cfg.get("enabled", True):
                continue

            rule = self._rules[rule_id]()
            rule_ctx = replace(ctx, params=cfg.get("params", {}) or {})

            try:
                result = rule.evaluate(rule_ctx)
            except Exception as exc:
                # A buggy rule must never break the pipeline or silently pass.
                log.warning("validation.rule_error", rule_id=rule_id, error=str(exc))
                result = ValidationResult(
                    rule_id=rule_id,
                    severity=Severity.SKIPPED,
                    reason=f"Rule raised {type(exc).__name__}: {exc}",
                    confidence=0.0,
                )

            # Config may downgrade/upgrade a violation's severity (policy, not logic).
            override = cfg.get("severity")
            if override and result.severity in (Severity.FAIL, Severity.WARNING):
                result = result.model_copy(update={"severity": Severity(override)})

            results.append(result)

        counts = {s.value: sum(1 for r in results if r.severity is s) for s in Severity}
        overall = max(
            (r.severity for r in results),
            key=lambda s: _SEVERITY_ORDER[s],
            default=Severity.PASS,
        )
        if overall is Severity.SKIPPED:
            overall = Severity.PASS

        return ValidationReport(overall=overall, results=results, counts=counts)
