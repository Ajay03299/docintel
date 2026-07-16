from app.engines.validation.base import ValidationContext, ValidationRule
from app.engines.validation.registry import register_rule
from app.schemas.validation import ValidationResult


@register_rule
class VendorKnownRule(ValidationRule):
    rule_id = "vendor_known"
    description = "Vendor must exist in the vendor directory."

    def evaluate(self, ctx: ValidationContext) -> ValidationResult:
        if ctx.vendor_directory is None:
            return self.skip("No vendor directory configured.", fields=["vendor_name"])
        vendor = ctx.data.get("vendor_name")
        if not vendor:
            return self.skip("No vendor_name to look up.", fields=["vendor_name"])
        if ctx.vendor_directory.is_known(str(vendor)):
            return self.ok(f"Vendor {vendor!r} is a known supplier.", fields=["vendor_name"])
        return self.warn(
            f"Vendor {vendor!r} is not in the vendor directory.",
            suggested_fix=(
                "Either onboard the vendor or verify the name was extracted correctly "
                "(OCR variants and legal-suffix differences are common)."
            ),
            fields=["vendor_name"],
        )
