INVOICE_SYSTEM_PROMPT = """You are a precise invoice data extraction engine.
Extract ONLY information present in the document. Never guess or invent values.
If a field is genuinely not present, use null. Return currency amounts as plain
numbers without symbols or thousands separators."""

# Field guidance lives in the PROMPT, not only in the Pydantic schema:
# Ollama's `format` parameter compiles the schema into a decoding grammar that
# constrains STRUCTURE (keys and types) — the model does not read schema
# descriptions. Semantic guidance must be in the prompt to have any effect.
_FIELD_GUIDE = """Field definitions:
- invoice_number: the invoice identifier, labelled 'Invoice Number', 'Invoice No', 'Invoice #'.
- invoice_date: the issue date, as written in the document.
- vendor_name: the company ISSUING the invoice (the seller being paid). This is
  normally the most prominent company name at the TOP of the document. It is NOT
  the customer, which appears under 'Bill To' / 'Ship To' / 'Customer'.
- vendor_tax_id: tax registration number of the issuing company (GST/VAT/TIN/EIN).
- currency: three-letter ISO code (USD, EUR, INR, GBP). Infer from an explicit
  code or from symbols: $ -> USD, EUR, £ -> GBP.
- subtotal: the amount BEFORE tax and discount, labelled 'Subtotal' or 'Net Amount'.
- tax_amount: the tax AMOUNT, not the percentage. For 'Tax (18%): 18.00' extract 18.00.
- discount: total discount applied, as a positive number.
- total: the final amount payable, labelled 'Total', 'Grand Total', 'Amount Due'.
- line_items: one entry per product/service row in the invoice table."""


def build_invoice_prompt(document_text: str) -> str:
    return (
        f"{_FIELD_GUIDE}\n\n"
        "Extract these fields from the document below.\n\n"
        "=== DOCUMENT TEXT START ===\n"
        f"{document_text}\n"
        "=== DOCUMENT TEXT END ===\n"
    )
