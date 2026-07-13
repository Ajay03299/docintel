import pytest

from app.engines.ingestion.service import (
    FileTooLarge,
    IngestionService,
    UnsupportedFileType,
)
from app.schemas.envelope import SourceChannel

PDF = b"%PDF-1.4 minimal fake body"


class FakeStorage:
    def __init__(self) -> None:
        self.saved: dict[str, bytes] = {}

    def save(self, data: bytes, *, suffix: str) -> str:
        key = f"k{len(self.saved)}{suffix}"
        self.saved[key] = data
        return key

    def load(self, key: str) -> bytes:
        return self.saved[key]


def test_ingest_pdf_ok():
    svc = IngestionService(storage=FakeStorage(), max_bytes=1000)
    env = svc.ingest(data=PDF, filename="a.pdf", channel=SourceChannel.REST_UPLOAD)
    assert env.content_type == "application/pdf"
    assert env.size_bytes == len(PDF)
    assert len(env.checksum_sha256) == 64


def test_reject_unsupported_type():
    svc = IngestionService(storage=FakeStorage(), max_bytes=1000)
    with pytest.raises(UnsupportedFileType):
        svc.ingest(data=b"plain text", filename="a.txt", channel=SourceChannel.REST_UPLOAD)


def test_reject_too_large():
    svc = IngestionService(storage=FakeStorage(), max_bytes=5)
    with pytest.raises(FileTooLarge):
        svc.ingest(data=PDF, filename="a.pdf", channel=SourceChannel.REST_UPLOAD)


def test_extension_spoofing_is_rejected():
    """.pdf name but non-PDF bytes → rejected. Security regression guard."""
    svc = IngestionService(storage=FakeStorage(), max_bytes=1000)
    with pytest.raises(UnsupportedFileType):
        svc.ingest(data=b"<html>gotcha</html>", filename="evil.pdf", channel=SourceChannel.REST_UPLOAD)