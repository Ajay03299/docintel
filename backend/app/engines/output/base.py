from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExportContext:
    """Everything an exporter may render. Exporters are pure functions of this:
    no DB, no filesystem — they return bytes and the caller decides where they go."""

    document_id: str
    filename: str
    data: dict
    confidence: dict = field(default_factory=dict)
    validation: dict = field(default_factory=dict)
    review: dict | None = None
    options: dict[str, Any] = field(default_factory=dict)


class Exporter(ABC):
    """Contract for every output format."""

    format_id: str = ""
    media_type: str = "application/octet-stream"
    extension: str = ".bin"

    @abstractmethod
    def render(self, ctx: ExportContext) -> bytes: ...

    def filename_for(self, ctx: ExportContext) -> str:
        stem = ctx.filename.rsplit(".", 1)[0] or ctx.document_id
        return f"{stem}{self.extension}"
