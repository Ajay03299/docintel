from app.engines.validation.base import ValidationContext, ValidationRule
from app.engines.validation.registry import register_rule
from app.schemas.validation import ValidationResult


def _num(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


@register_rule
class InvoiceTotalArithmeticRule(ValidationRule):
    rule_id = "invoice_total_arithmetic"
    description = "subtotal + tax - discount must equal total."

    def evaluate(self, ctx: ValidationContext) -> ValidationResult:
        tol = ctx.params.get("tolerance", 0.01)
        subtotal, tax = _num(ctx.data.get("subtotal")), _num(ctx.data.get("tax_amount"))
        discount = _num(ctx.data.get("discount")) or 0.0
        total = _num(ctx.data.get("total"))
        if subtotal is None or total is None:
            return self.skip(
                "Cannot check totals: subtotal or total is missing.",
                fields=["subtotal", "total"],
            )
        tax = tax or 0.0
        expected = subtotal + tax - discount
        delta = abs(expected - total)
        if delta <= tol:
            return self.ok(
                f"Total balances: {subtotal:.2f} + {tax:.2f} - {discount:.2f} = {total:.2f}.",
                fields=["subtotal", "tax_amount", "discount", "total"],
            )
        return self.fail(
            f"Total does not balance: expected {expected:.2f} "
            f"({subtotal:.2f} + {tax:.2f} - {discount:.2f}) but document states "
            f"{total:.2f} (difference {delta:.2f}).",
            suggested_fix=(
                f"Set total to {expected:.2f}, or re-extract the numeric fields — a "
                f"difference of {delta:.2f} often means one component was misread."
            ),
            fields=["subtotal", "tax_amount", "discount", "total"],
        )


@register_rule
class SubtotalMatchesLineItemsRule(ValidationRule):
    rule_id = "subtotal_matches_line_items"
    description = "Sum of line item amounts must equal the stated subtotal."

    def evaluate(self, ctx: ValidationContext) -> ValidationResult:
        tol = ctx.params.get("tolerance", 0.01)
        subtotal = _num(ctx.data.get("subtotal"))
        items = ctx.data.get("line_items") or []
        if subtotal is None:
            return self.skip("No subtotal to compare against.", fields=["subtotal"])
        if not items:
            return self.skip("No line items extracted.", fields=["line_items"])
        amounts = [_num(i.get("amount")) for i in items if isinstance(i, dict)]
        if any(a is None for a in amounts):
            return self.warn(
                f"{sum(a is None for a in amounts)} of {len(amounts)} line items have "
                "no amount; subtotal cannot be verified.",
                suggested_fix="Re-extract line items or have a reviewer complete them.",
                fields=["line_items", "subtotal"],
            )
        summed = sum(amounts)
        if abs(summed - subtotal) <= tol:
            return self.ok(
                f"Line items sum to {summed:.2f}, matching subtotal.",
                fields=["line_items", "subtotal"],
            )
        return self.fail(
            f"Line items sum to {summed:.2f} but subtotal states {subtotal:.2f} "
            f"(difference {abs(summed - subtotal):.2f}).",
            suggested_fix=(
                "A line item was likely missed or double-counted; compare the item "
                "count against the source table."
            ),
            fields=["line_items", "subtotal"],
        )


@register_rule
class LineItemAmountConsistencyRule(ValidationRule):
    rule_id = "line_item_amount_consistency"
    description = "Each line item's quantity x unit_price must equal its amount."

    def evaluate(self, ctx: ValidationContext) -> ValidationResult:
        tol = ctx.params.get("tolerance", 0.01)
        items = ctx.data.get("line_items") or []
        if not items:
            return self.skip("No line items extracted.", fields=["line_items"])
        bad: list[str] = []
        checked = 0
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            qty, price, amount = (
                _num(item.get("quantity")),
                _num(item.get("unit_price")),
                _num(item.get("amount")),
            )
            if None in (qty, price, amount):
                continue
            checked += 1
            if abs(qty * price - amount) > tol:
                bad.append(
                    f"item {idx + 1} ({item.get('description', '?')}): "
                    f"{qty:g} x {price:.2f} = {qty * price:.2f}, stated {amount:.2f}"
                )
        if checked == 0:
            return self.skip("No line items had all of qty/price/amount.", fields=["line_items"])
        if not bad:
            return self.ok(f"All {checked} line item(s) internally consistent.", fields=["line_items"])
        return self.fail(
            f"{len(bad)} of {checked} line item(s) inconsistent: " + "; ".join(bad),
            suggested_fix="Re-extract these rows; column misalignment is the usual cause.",
            fields=["line_items"],
        )


@register_rule
class TaxPercentageRule(ValidationRule):
    rule_id = "tax_percentage_plausible"
    description = "Implied tax rate (tax/subtotal) must fall in a plausible band."

    def evaluate(self, ctx: ValidationContext) -> ValidationResult:
        max_pct = ctx.params.get("max_percent", 30.0)
        known = ctx.params.get("known_rates", [0, 5, 8, 12, 18, 20, 28])
        tol = ctx.params.get("rate_tolerance", 0.6)
        subtotal, tax = _num(ctx.data.get("subtotal")), _num(ctx.data.get("tax_amount"))
        if subtotal is None or tax is None:
            return self.skip("Need both subtotal and tax_amount.", fields=["subtotal", "tax_amount"])
        if subtotal <= 0:
            return self.skip("Subtotal is not positive; rate undefined.", fields=["subtotal"])
        pct = tax / subtotal * 100
        if pct > max_pct:
            return self.fail(
                f"Implied tax rate {pct:.1f}% exceeds the maximum plausible {max_pct:.0f}%.",
                suggested_fix="A tax percentage was likely extracted as an amount, or vice versa.",
                fields=["tax_amount", "subtotal"],
            )
        if any(abs(pct - r) <= tol for r in known):
            return self.ok(f"Implied tax rate {pct:.1f}% matches a standard rate.",
                           fields=["tax_amount", "subtotal"])
        return self.warn(
            f"Implied tax rate {pct:.1f}% is plausible but matches no standard rate {known}.",
            confidence=0.6,
            suggested_fix="Confirm the jurisdiction's rate, or check for a rounding error.",
            fields=["tax_amount", "subtotal"],
        )
