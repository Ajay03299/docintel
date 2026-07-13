from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None


class InvoiceData(BaseModel):
    """Target extraction schema for invoices. Every field optional — a small
    local model WILL miss fields, and we capture partial data rather than
    throwing. Missing fields surface as low confidence downstream."""
    invoice_number: str | None = None
    invoice_date: str | None = None
    vendor_name: str | None = None
    vendor_tax_id: str | None = None
    currency: str | None = None
    subtotal: float | None = None
    tax_amount: float | None = None
    discount: float | None = None
    total: float | None = None
    line_items: list[LineItem] = Field(default_factory=list)