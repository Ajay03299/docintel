import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.engines.ingestion.service import (
    FileTooLarge,
    IngestionService,
    UnsupportedFileType,
)
from app.engines.ingestion.storage import get_storage
from app.models.document import Document, DocumentStatus
from app.schemas.envelope import SourceChannel

log = structlog.get_logger()
router = APIRouter(tags=["documents"])


def get_ingestion_service() -> IngestionService:
    settings = get_settings()
    return IngestionService(storage=get_storage(settings), max_bytes=settings.max_upload_bytes)


@router.post("/documents", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    service: IngestionService = Depends(get_ingestion_service),
):
    data = await file.read()
    try:
        envelope = service.ingest(
            data=data, filename=file.filename or "unknown", channel=SourceChannel.REST_UPLOAD
        )
    except FileTooLarge:
        raise HTTPException(413, "File too large")
    except UnsupportedFileType:
        raise HTTPException(415, "Unsupported file type")

    doc = Document(
        id=envelope.document_id,
        status=DocumentStatus.UPLOADED,
        source_channel=envelope.source_channel.value,
        original_filename=envelope.original_filename,
        content_type=envelope.content_type,
        size_bytes=envelope.size_bytes,
        storage_key=envelope.storage_key,
        checksum_sha256=envelope.checksum_sha256,
    )
    db.add(doc)
    db.commit()
    log.info("document.ingested", document_id=str(doc.id), content_type=doc.content_type, size=doc.size_bytes)
    # TODO(Day 3): enqueue Celery processing task here, return immediately.
    return {"document_id": str(doc.id), "status": doc.status.value}