import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.engines.ingestion.service import (
    FileTooLarge,
    IngestionService,
    UnsupportedFileType,
)
from app.engines.ingestion.storage import get_storage
from app.models.document import Document, DocumentStatus
from app.models.extraction import Extraction
from app.models.validation import Validation
from app.models.review import Review
from app.schemas.envelope import SourceChannel

log = structlog.get_logger()
router = APIRouter(tags=["documents"])


def get_ingestion_service() -> IngestionService:
    settings = get_settings()
    return IngestionService(storage=get_storage(settings), max_bytes=settings.max_upload_bytes)


@router.post("/documents", status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    service: IngestionService = Depends(get_ingestion_service),
    _identity: str = Depends(rate_limit),
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

    # Enqueue async processing; return immediately (do NOT block on the 6s+ LLM call).
    from app.workers.pipeline import process_document
    process_document.delay(str(doc.id))

    return {"document_id": str(doc.id), "status": doc.status.value}

@router.get("/documents/{document_id}")
def get_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    ext = db.query(Extraction).filter_by(document_id=doc.id).one_or_none()
    val = db.query(Validation).filter_by(document_id=doc.id).one_or_none()
    rev = db.query(Review).filter_by(document_id=doc.id).one_or_none()
    return {
        "document_id": str(doc.id),
        "status": doc.status.value,
        "filename": doc.original_filename,
        "extraction": None if ext is None else {
            "method": ext.extraction_method,
            "model": ext.model,
            "data": ext.data,
            "overall_confidence": ext.overall_confidence,
            "confidence": ext.confidence,
            "parse_error": ext.parse_error,
        },
        "validation": None if val is None else {
            "overall": val.overall,
            "report": val.report,
        },
        "review": None if rev is None else {
            "decision": rev.decision,
            "reasoning": rev.reasoning,
            "attempts": rev.attempts,
            "overridden": rev.overridden,
            "override_reason": rev.override_reason,
            "history": rev.history,
        },
    }


@router.get("/documents/{document_id}/export")
def export_document(
    document_id: str,
    format: str = Query("json", description="Export format id"),
    include_evidence: bool = Query(False),
    db: Session = Depends(get_db),
):
    from app.engines.output.base import ExportContext
    from app.engines.output.registry import get_exporter, get_exporters

    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    ext = db.query(Extraction).filter_by(document_id=doc.id).one_or_none()
    if ext is None:
        raise HTTPException(409, "Document has no extraction to export yet")

    try:
        exporter = get_exporter(format)
    except ValueError:
        raise HTTPException(400, f"Unknown format {format!r}. Available: {sorted(get_exporters())}")

    val = db.query(Validation).filter_by(document_id=doc.id).one_or_none()
    rev = db.query(Review).filter_by(document_id=doc.id).one_or_none()

    ctx = ExportContext(
        document_id=str(doc.id),
        filename=doc.original_filename,
        data=ext.data or {},
        confidence=ext.confidence or {},
        validation=(val.report if val else {}),
        review=({"decision": rev.decision, "reasoning": rev.reasoning} if rev else None),
        options={"include_evidence": include_evidence},
    )
    body = exporter.render(ctx)
    return Response(
        content=body,
        media_type=exporter.media_type,
        headers={"Content-Disposition": f'attachment; filename="{exporter.filename_for(ctx)}"'},
    )


@router.get("/export-formats")
def list_export_formats():
    from app.engines.output.registry import get_exporters

    return {
        "formats": [
            {"id": fid, "media_type": cls.media_type, "extension": cls.extension}
            for fid, cls in sorted(get_exporters().items())
        ]
    }


@router.get("/documents")
def list_documents(
    status: str | None = Query(None, description="Filter by status, e.g. 'escalated'"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Document)
    if status:
        try:
            q = q.filter(Document.status == DocumentStatus(status))
        except ValueError:
            raise HTTPException(400, f"Unknown status {status!r}")
    total = q.count()
    rows = (
        q.order_by(Document.created_at.desc()).offset(offset).limit(limit).all()
    )
    items = []
    for d in rows:
        ext = db.query(Extraction).filter_by(document_id=d.id).one_or_none()
        val = db.query(Validation).filter_by(document_id=d.id).one_or_none()
        rev = db.query(Review).filter_by(document_id=d.id).one_or_none()
        items.append({
            "document_id": str(d.id),
            "filename": d.original_filename,
            "status": d.status.value,
            "created_at": d.created_at.isoformat(),
            "overall_confidence": ext.overall_confidence if ext else None,
            "validation": val.overall if val else None,
            "review_decision": rev.decision if rev else None,
        })
    return {"total": total, "limit": limit, "offset": offset, "items": items}
