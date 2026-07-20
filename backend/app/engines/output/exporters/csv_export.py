import csv
import io

from app.engines.output.base import ExportContext, Exporter
from app.engines.output.registry import register_exporter

_HEADER_FIELDS = (
    "invoice_number", "invoice_date", "vendor_name", "vendor_tax_id",
    "currency", "subtotal", "tax_amount", "discount", "total",
)


@register_exporter
class CsvExporter(Exporter):
    """One row per line item, header fields repeated — the shape accounting
    systems expect for bulk import."""

    format_id = "csv"
    media_type = "text/csv"
    extension = ".csv"

    def render(self, ctx: ExportContext) -> bytes:
        buf = io.StringIO()
        cols = [*_HEADER_FIELDS, "line_description", "line_quantity",
                "line_unit_price", "line_amount"]
        writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()

        header = {k: ctx.data.get(k) for k in _HEADER_FIELDS}
        items = ctx.data.get("line_items") or []
        if not items:
            writer.writerow(header)
        for item in items:
            writer.writerow({
                **header,
                "line_description": item.get("description"),
                "line_quantity": item.get("quantity"),
                "line_unit_price": item.get("unit_price"),
                "line_amount": item.get("amount"),
            })
        return buf.getvalue().encode()
