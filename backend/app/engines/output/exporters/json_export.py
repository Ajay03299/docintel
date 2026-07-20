import json

from app.engines.output.base import ExportContext, Exporter
from app.engines.output.registry import register_exporter


@register_exporter
class JsonExporter(Exporter):
    format_id = "json"
    media_type = "application/json"
    extension = ".json"

    def render(self, ctx: ExportContext) -> bytes:
        payload: dict = {"document_id": ctx.document_id, "data": ctx.data}
        # Audit trail is opt-in: downstream ERPs want the data, auditors want the
        # evidence. Same exporter, one flag.
        if ctx.options.get("include_evidence", False):
            payload["confidence"] = ctx.confidence
            payload["validation"] = ctx.validation
            payload["review"] = ctx.review
        indent = ctx.options.get("indent", 2)
        return json.dumps(payload, indent=indent, default=str).encode()
