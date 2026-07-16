from app.engines.validation.base import ValidationContext, ValidationRule
from app.engines.validation.registry import register_rule
from app.schemas.validation import ValidationResult


def _num(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


@register_rule
class NegativeQuantityRule(ValidationRule):
    rule_id = "negative_quantity"
    description = "Line item quantities must not be negative or zero."

    def evaluate(self, ctx: ValidationContext) -> ValidationResult:
        allow_zero = ctx.params.get("allow_zero", False)
        items = ctx.data.get("line_items") or []
        if not items:
            return self.skip("No line items extracted.", fields=["line_items"])
        bad = []
        for idx, item in enumerate(items):
            qty = _num(item.get("quantity")) if isinstance(item, dict) else None
            if qty is None:
                continue
            if qty < 0 or (qty == 0 and not allow_zero):
                bad.append(f"item {idx + 1} qty={qty:g}")
        if not bad:
            return self.ok("All line item quantities are positive.", fields=["line_items"])
        return self.fail(
            f"Invalid quantity on {len(bad)} line(s): {', '.join(bad)}.",
            suggested_fix=(
                "Negative quantities usually indicate a credit note misclassified as "
                "an invoice, or a misread minus sign."
            ),
            fields=["line_items"],
        )


@register_rule
class NegativeAmountRule(ValidationRule):
    rule_id = "negative_amount"
    description = "Monetary totals must not be negative."

    def evaluate(self, ctx: ValidationContext) -> ValidationResult:
        checked, bad = [], []
        for name in ("subtotal", "tax_amount", "total", "discount"):
            v = _num(ctx.data.get(name))
            if v is None:
                continue
            checked.append(name)
            if v < 0:
                bad.append(f"{name}={v:.2f}")
        if not checked:
            return self.skip("No monetary fields present.", fields=["total"])
        if not bad:
            return self.ok(f"All {len(checked)} monetary field(s) non-negative.", fields=checked)
        return self.fail(
            f"Negative monetary value(s): {', '.join(bad)}.",
            suggested_fix="Check whether this is a credit note rather than an invoice.",
            fields=[b.split("=")[0] for b in bad],
        )


@register_rule
class ZeroTotalRule(ValidationRule):
    rule_id = "zero_total"
    description = "An invoice total of zero is suspicious."

    def evaluate(self, ctx: ValidationContext) -> ValidationResult:
        total = _num(ctx.data.get("total"))
        if total is None:
            return self.skip("No total present.", fields=["total"])
        if total == 0:
            return self.warn(
                "Invoice total is 0.00.",
                suggested_fix="Verify: legitimate zero-value invoices exist but are rare.",
                fields=["total"],
            )
        return self.ok(f"Total {total:.2f} is non-zero.", fields=["total"])
