import structlog
from celery.exceptions import SoftTimeLimitExceeded

from app.core.config import get_settings
from app.db.session import session_scope
from app.engines.confidence.service import ConfidenceService
from app.engines.ingestion.storage import get_storage
from app.engines.understanding.extraction import (
    ExtractionService,
    NativeExtractor,
    OcrExtractor,
    normalize_text,
)
from app.engines.understanding.providers.ollama import OllamaProvider
from app.engines.understanding.structured_extraction import StructuredExtractor
from app.models.document import Document, DocumentStatus
from app.models.extraction import Extraction
from app.plugins.invoice.confidence import (
    CRITICAL_FIELDS,
    FIELD_WEIGHTS,
    build_field_scores,
)
from app.plugins.invoice.prompt import INVOICE_SYSTEM_PROMPT, build_invoice_prompt
from app.plugins.invoice.schema import InvoiceData
from app.workers.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=5,
    acks_late=True,
)
def process_document(self, document_id: str) -> dict:
    """End-to-end processing for one document. Idempotent and resumable:
    resumes from the document's current status; on unrecoverable failure the
    document is moved to FAILED with a reason (never left stuck in PROCESSING)."""
    settings = get_settings()
    log.info("pipeline.start", document_id=document_id, attempt=self.request.retries)

    try:
        with session_scope() as db:
            doc = db.get(Document, document_id)
            if doc is None:
                log.error("pipeline.doc_missing", document_id=document_id)
                return {"status": "missing"}

            # Idempotency/resume guard: if already past extraction, don't redo it.
            if doc.status in (
                DocumentStatus.EXTRACTED,
                DocumentStatus.VALIDATED,
                DocumentStatus.COMPLETED,
            ):
                log.info(
                    "pipeline.already_done",
                    document_id=document_id,
                    status=doc.status.value,
                )
                return {"status": doc.status.value}

            doc.status = DocumentStatus.PROCESSING
            db.flush()

            storage = get_storage(settings)
            data = storage.load(doc.storage_key)

            # --- Stage 1: text extraction (native/OCR decision) ---
            ext_svc = ExtractionService(NativeExtractor(), OcrExtractor())
            text_result = ext_svc.extract(data, doc.content_type)
            # Strip PDF column padding before the LLM sees it: deterministic
            # cleanup removes noise far more cheaply than prompting around it.
            clean_text = normalize_text(text_result.full_text)

            # --- Stage 2: structured LLM extraction ---
            provider = OllamaProvider(settings.ollama_base_url, settings.ollama_model)
            structured = StructuredExtractor(provider, max_retries=1).extract(
                document_text=clean_text,
                system_prompt=INVOICE_SYSTEM_PROMPT,
                user_prompt=build_invoice_prompt(clean_text),
                schema_model=InvoiceData,
            )

            # --- Stage 3: confidence scoring (deterministic verification) ---
            scores = build_field_scores(structured.data, clean_text)
            report = ConfidenceService(settings.confidence_strategy).build_report(
                scores=scores, weights=FIELD_WEIGHTS, critical=CRITICAL_FIELDS
            )

            # --- Persist checkpoint: upsert extraction (idempotent) ---
            existing = db.query(Extraction).filter_by(document_id=doc.id).one_or_none()
            if existing is None:
                existing = Extraction(document_id=doc.id)
                db.add(existing)
            existing.extraction_method = text_result.method.value
            existing.model = structured.model
            existing.data = structured.data
            existing.parse_error = structured.parse_error
            existing.overall_confidence = report.overall
            existing.confidence = report.model_dump()

            doc.status = DocumentStatus.EXTRACTED
            log.info(
                "pipeline.extracted",
                document_id=document_id,
                method=text_result.method.value,
                parse_error=structured.parse_error,
                confidence=report.overall,
                strategy=report.strategy,
            )
            return {
                "status": "extracted",
                "confidence": report.overall,
                "parse_error": structured.parse_error,
            }

    except SoftTimeLimitExceeded:
        # Ran out of time — mark FAILED, do not retry into another timeout.
        _mark_failed(document_id, "soft time limit exceeded")
        raise
    except Exception as exc:
        log.warning(
            "pipeline.error",
            document_id=document_id,
            error=str(exc),
            attempt=self.request.retries,
        )
        try:
            raise self.retry(exc=exc)  # bounded retry with backoff
        except self.MaxRetriesExceededError:
            _mark_failed(document_id, f"max retries exceeded: {exc}")
            return {"status": "failed"}


def _mark_failed(document_id: str, reason: str) -> None:
    """Terminal failure: document -> FAILED with reason. Never left in PROCESSING."""
    with session_scope() as db:
        doc = db.get(Document, document_id)
        if doc is not None:
            doc.status = DocumentStatus.FAILED
            doc.doc_metadata = {
                **(doc.doc_metadata or {}),
                "failure_reason": reason,
            }
    log.error("pipeline.failed", document_id=document_id, reason=reason)
