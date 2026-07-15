from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str | None = Field(
        default=None, description="Text description of the product or service"
    )
    quantity: float | None = Field(default=None, description="Number of units")
    unit_price: float | None = Field(default=None, description="Price per single unit")
    amount: float | None = Field(
        default=None, description="Line total, usually quantity * unit_price"
    )


class InvoiceData(BaseModel):
    """Target extraction schema for invoices.

    Every field is optional: a small local model WILL miss fields, and we
    capture partial data rather than throwing. Missing fields surface as
    zero confidence downstream rather than as exceptions.

    Field descriptions are not documentation only — Ollama passes this JSON
    schema into constrained decoding, so descriptions directly steer extraction.
    """

    invoice_number: str | None = Field(
        default=None,
        description="The invoice identifier, e.g. 'INV-2026-0042'. Labelled "
        "'Invoice Number', 'Invoice No', 'Invoice #' or similar.",
    )
    invoice_date: str | None = Field(
        default=None,
        description="The date the invoice was issued, as it appears in the document.",
    )
    vendor_name: str | None = Field(
        default=None,
        description="The company ISSUING the invoice (the seller/supplier being paid). "
        "Usually the most prominent company name at the top of the document, "
        "NOT the customer listed under 'Bill To' or 'Ship To'.",
    )
    vendor_tax_id: str | None = Field(
        default=None,
        description="Tax registration number of the issuing company (GST/VAT/TIN/EIN).",
    )
    currency: str | None = Field(
        default=None,
        description="Three-letter ISO currency code, e.g. USD, EUR, INR. Infer from "
        "an explicit code or from currency symbols ($ -> USD, EUR, £ -> GBP).",
    )
    subtotal: float | None = Field(
        default=None,
        description="Sum of line items BEFORE tax and discount. Labelled 'Subtotal', "
        "'Net Amount', 'Amount before tax' or similar.",
    )
    tax_amount: float | None = Field(
        default=None,
        description="Total tax charged as a number, e.g. for 'Tax (18%): 18.00' "
        "extract 18.00 (the amount, not the percentage).",
    )
    discount: float | None = Field(
        default=None, description="Total discount applied, as a positive number."
    )
    total: float | None = Field(
        default=None,
        description="The final amount payable. Labelled 'Total', 'Grand Total', "
        "'Amount Due', 'Balance Due' or similar.",
    )
    line_items: list[LineItem] = Field(
        default_factory=list,
        description="Each individual product/service row in the invoice table.",
    )
