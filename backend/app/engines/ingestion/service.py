import hashlib

from app.engines.ingestion.storage import Storage
from app.engines.ingestion.validation import sniff_content_type
from app.schemas.envelope import DocumentEnvelope, SourceChannel

ALLOWED = {"application/pdf", "image/png", "image/jpeg"}
_SUFFIX = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}


class UnsupportedFileType(Exception): ...
class FileTooLarge(Exception): ...


class IngestionService:
    def __init__(self, storage: Storage, max_bytes: int) -> None:
        self._storage = storage
        self._max_bytes = max_bytes

    def ingest(self, *, data: bytes, filename: str, channel: SourceChannel) -> DocumentEnvelope:
        if len(data) > self._max_bytes:
            raise FileTooLarge(f"{len(data)} bytes exceeds limit {self._max_bytes}")

        content_type = sniff_content_type(data)
        if content_type not in ALLOWED:
            raise UnsupportedFileType(f"Detected type {content_type!r} not allowed")

        checksum = hashlib.sha256(data).hexdigest()
        key = self._storage.save(data, suffix=_SUFFIX[content_type])
        return DocumentEnvelope(
            source_channel=channel,
            original_filename=filename,
            content_type=content_type,
            size_bytes=len(data),
            storage_key=key,
            checksum_sha256=checksum,
        )