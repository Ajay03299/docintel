import re

from app.engines.validation.base import ValidationContext, ValidationRule
from app.engines.validation.registry import register_rule
from app.schemas.validation import ValidationResult

_DEFAULT_REQUIRED = ["invoice_number", "invoice_date", "vendor_name", "total"]
_ISO_CURRENCY = re.compile(r"^[A-Z]{3}$")
_GSTIN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_EU_VAT = re.compile(r"^[A-Z]{2}[0-9A-Z]{8,12}$")
_US_EIN = re.compile(r"^[0-9]{2}-[0-9]{7}$")


def _missing(data: dict, keys: list[str]) -> list[str]:
    out = []
    for k in keys:
        v = data.get(k)
        if v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and not v):
            out.append(k)
    return out


@register_rule
class MandatoryFieldsRule(ValidationRule):
    rule_id = "mandatory_fields"
    description = "Required invoice fields must be present and non-empty."

    def evaluate(self, ctx: ValidationContext) -> ValidationResult:
        required = ctx.params.get("required", _DEFAULT_REQUIRED)
        missing = _missing(ctx.data, required)
        if not missing:
            return self.ok(f"All {len(required)} mandatory fields present.", fields=required)
        return self.fail(
            f"Missing mandatory field(s): {', '.join(missing)}.",
            suggested_fix=(
                "Re-run extraction, or have a reviewer key these fields in manually "
                "from the source document."
            ),
            fields=missing,
        )


@register_rule
class InvoiceNumberFormatRule(ValidationRule):
    rule_id = "invoice_number_format"
    description = "Invoice number must look like an identifier, not prose."

    def evaluate(self, ctx: ValidationContext) -> ValidationResult:
        value = ctx.data.get("invoice_number")
        if not value:
            return self.skip("No invoice_number to check.", fields=["invoice_number"])
        min_len = ctx.params.get("min_length", 3)
        max_len = ctx.params.get("max_length", 40)
        pattern = ctx.params.get("pattern", r"^[A-Za-z0-9][A-Za-z0-9\-_/\.]*$")
        text = str(value).strip()
        if not (min_len <= len(text) <= max_len):
            return self.warn(
                f"Invoice number {text!r} has implausible length {len(text)} "
                f"(expected {min_len}-{max_len}).",
                suggested_fix="Verify the invoice number against the document header.",
                fields=["invoice_number"],
            )
        if not re.match(pattern, text):
            return self.warn(
                f"Invoice number {text!r} contains unexpected characters.",
                suggested_fix="Check the extractor did not capture a label or sentence.",
                fields=["invoice_number"],
            )
        return self.ok(f"Invoice number {text!r} is well-formed.", fields=["invoice_number"])


@register_rule
class CurrencyValidRule(ValidationRule):
    rule_id = "currency_valid"
    description = "Currency must be a 3-letter ISO 4217 code from the allowed list."

    def evaluate(self, ctx: ValidationContext) -> ValidationResult:
        value = ctx.data.get("currency")
        if not value:
            return self.warn(
                "Currency is absent; amounts cannot be interpreted unambiguously.",
                suggested_fix="Default to the vendor's usual currency or ask a reviewer.",
                fields=["currency"],
            )
        code = str(value).strip().upper()
        if not _ISO_CURRENCY.match(code):
            return self.fail(
                f"Currency {value!r} is not a 3-letter ISO 4217 code.",
                suggested_fix="Map symbols to codes ($ -> USD, EUR).",
                fields=["currency"],
            )
        allowed = ctx.params.get("allowed")
        if allowed and code not in allowed:
            return self.warn(
                f"Currency {code} is valid ISO but outside the accepted list {allowed}.",
                suggested_fix="Confirm this vendor is approved to bill in this currency.",
                fields=["currency"],
            )
        return self.ok(f"Currency {code} is a valid ISO code.", fields=["currency"])


@register_rule
class VendorTaxIdFormatRule(ValidationRule):
    rule_id = "vendor_tax_id_format"
    description = "Vendor tax ID (GSTIN/VAT/EIN) must match a known format."

    def evaluate(self, ctx: ValidationContext) -> ValidationResult:
        value = ctx.data.get("vendor_tax_id")
        if not value:
            return self.skip("No vendor_tax_id present.", fields=["vendor_tax_id"])
        text = str(value).strip().upper().replace(" ", "")
        for name, pattern in (("GSTIN", _GSTIN), ("EU VAT", _EU_VAT), ("US EIN", _US_EIN)):
            if pattern.match(text):
                return self.ok(f"Tax ID matches {name} format.", fields=["vendor_tax_id"])
        return self.warn(
            f"Tax ID {text!r} matches no known GSTIN/VAT/EIN format.",
            suggested_fix="Verify against the vendor master record; may be OCR noise.",
            fields=["vendor_tax_id"],
        )
