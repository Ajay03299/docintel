from xml.etree.ElementTree import Element, SubElement, tostring

from app.engines.output.base import ExportContext, Exporter
from app.engines.output.registry import register_exporter


@register_exporter
class XmlExporter(Exporter):
    format_id = "xml"
    media_type = "application/xml"
    extension = ".xml"

    def render(self, ctx: ExportContext) -> bytes:
        root = Element("invoice", {"documentId": ctx.document_id})
        for key, value in ctx.data.items():
            if key == "line_items":
                continue
            SubElement(root, key).text = "" if value is None else str(value)
        items_el = SubElement(root, "lineItems")
        for item in ctx.data.get("line_items") or []:
            el = SubElement(items_el, "lineItem")
            for k, v in item.items():
                SubElement(el, k).text = "" if v is None else str(v)
        return b'<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(root, encoding="utf-8")
