from datetime import datetime, timezone

from app.core.dates import DATE_FORMATS, parse_date
from app.engines.validation.base import ValidationContext, ValidationRule
from app.engines.validation.registry import register_rule
from app.schemas.validation import ValidationResult


def _now(ctx: ValidationContext) -> datetime:
    """Clock comes from the context so date rules are deterministic in tests."""
    return ctx.now or datetime.now(timezone.utc).replace(tzinfo=None)


@register_rule
class DateFormatRule(ValidationRule):
    retryable = True
    rule_id = "date_format_valid"
    description = "Invoice date must parse as a real calendar date."

    def evaluate(self, ctx: ValidationContext) -> ValidationResult:
        raw = ctx.data.get("invoice_date")
        if not raw:
            return self.skip("No invoice_date present.", fields=["invoice_date"])
        if parse_date(raw) is None:
            return self.fail(
                f"Invoice date {raw!r} does not parse in any known format.",
                suggested_fix=f"Expected one of: {', '.join(DATE_FORMATS[:4])}.",
                fields=["invoice_date"],
            )
        return self.ok(f"Invoice date {raw!r} parses correctly.", fields=["invoice_date"])


@register_rule
class FutureDateRule(ValidationRule):
    rule_id = "future_date"
    description = "Invoice date must not be in the future."

    def evaluate(self, ctx: ValidationContext) -> ValidationResult:
        grace = ctx.params.get("grace_days", 1)
        parsed = parse_date(ctx.data.get("invoice_date"))
        if parsed is None:
            return self.skip("No parseable invoice_date.", fields=["invoice_date"])
        days_ahead = (parsed - _now(ctx)).days
        if days_ahead > grace:
            return self.fail(
                f"Invoice is dated {days_ahead} day(s) in the future "
                f"({parsed.date()}).",
                suggested_fix=(
                    "Future-dated invoices are a common fraud and data-entry signal; "
                    "confirm the date with the vendor before payment."
                ),
                fields=["invoice_date"],
            )
        return self.ok(f"Invoice date {parsed.date()} is not in the future.",
                       fields=["invoice_date"])


@register_rule
class StaleDateRule(ValidationRule):
    rule_id = "stale_date"
    description = "Invoice should not be older than the configured window."

    def evaluate(self, ctx: ValidationContext) -> ValidationResult:
        max_age = ctx.params.get("max_age_days", 365)
        parsed = parse_date(ctx.data.get("invoice_date"))
        if parsed is None:
            return self.skip("No parseable invoice_date.", fields=["invoice_date"])
        age = (_now(ctx) - parsed).days
        if age > max_age:
            return self.warn(
                f"Invoice is {age} days old (limit {max_age}).",
                suggested_fix="Check whether this is a late submission or a duplicate re-send.",
                fields=["invoice_date"],
            )
        return self.ok(f"Invoice age {age} day(s) is within the {max_age}-day window.",
                       fields=["invoice_date"])
