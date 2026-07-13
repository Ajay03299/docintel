INVOICE_SYSTEM_PROMPT = """You are a precise invoice data extraction engine.
Extract ONLY information present in the document. Do not guess or invent values.
If a field is not present, use null. Return currency amounts as plain numbers
without symbols. Respond with a single JSON object matching the requested schema."""


def build_invoice_prompt(document_text: str) -> str:
    return (
        "Extract the invoice fields from the following document text.\n\n"
        "=== DOCUMENT TEXT START ===\n"
        f"{document_text}\n"
        "=== DOCUMENT TEXT END ===\n"
    )