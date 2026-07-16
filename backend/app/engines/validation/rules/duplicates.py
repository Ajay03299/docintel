from app.engines.validation.base import ValidationContext, ValidationRule
from app.engines.validation.registry import register_rule
from app.schemas.validation import ValidationResult


@register_rule
class DuplicateInvoiceRule(ValidationRule):
    rule_id = "duplicate_invoice"
    description = "Same vendor + invoice number must not already exist."

    def evaluate(self, ctx: ValidationContext) -> ValidationResult:
        if ctx.duplicate_lookup is None:
            return self.skip("No duplicate lookup configured.", fields=["invoice_number"])
        vendor, number = ctx.data.get("vendor_name"), ctx.data.get("invoice_number")
        if not vendor or not number:
            return self.skip(
                "Need both vendor_name and invoice_number to detect duplicates.",
                fields=["vendor_name", "invoice_number"],
            )
        matches = ctx.duplicate_lookup.find_duplicates(
            vendor_name=vendor,
            invoice_number=number,
            total=ctx.data.get("total"),
            exclude_document_id=ctx.document_id,
        )
        if not matches:
            return self.ok(
                f"No prior invoice {number!r} from {vendor!r}.",
                fields=["vendor_name", "invoice_number"],
            )
        return self.fail(
            f"Invoice {number!r} from {vendor!r} already exists "
            f"({len(matches)} match(es): {', '.join(matches[:3])}).",
            suggested_fix=(
                "Block payment pending review — duplicate invoices are the single "
                "most common accounts-payable loss."
            ),
            fields=["vendor_name", "invoice_number"],
        )


@register_rule
class DuplicateLineItemRule(ValidationRule):
    rule_id = "duplicate_line_items"
    description = "Identical line items repeated within one invoice are suspicious."

    def evaluate(self, ctx: ValidationContext) -> ValidationResult:
        items = ctx.data.get("line_items") or []
        if len(items) < 2:
            return self.skip("Fewer than two line items.", fields=["line_items"])
        seen: dict[tuple, int] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            key = (
                str(item.get("description", "")).strip().lower(),
                item.get("quantity"),
                item.get("unit_price"),
                item.get("amount"),
            )
            seen[key] = seen.get(key, 0) + 1
        dupes = {k: v for k, v in seen.items() if v > 1}
        if not dupes:
            return self.ok(f"All {len(items)} line items are distinct.", fields=["line_items"])
        detail = "; ".join(f"{k[0]!r} x{v}" for k, v in list(dupes.items())[:3])
        return self.warn(
            f"{len(dupes)} line item(s) appear more than once: {detail}.",
            suggested_fix=(
                "May be legitimate (same item, separate deliveries) or an extraction "
                "duplication — compare against the source table."
            ),
            fields=["line_items"],
        )
