import structlog
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import session_scope
from app.engines.confidence.service import ConfidenceService
from app.engines.ingestion.storage import get_storage
from app.engines.review.agent import ReviewAgent
from app.engines.understanding.extraction import (
    ExtractionService,
    NativeExtractor,
    OcrExtractor,
    normalize_text,
)
from app.engines.understanding.providers.base import LLMProvider
from app.engines.understanding.providers.ollama import OllamaProvider
from app.engines.understanding.structured_extraction import (
    StructuredExtractionResult,
    StructuredExtractor,
)
from app.engines.validation.adapters import SqlDuplicateLookup, load_vendor_directory
from app.engines.validation.base import ValidationContext
from app.engines.validation.config import invoice_rule_config
from app.engines.validation.service import ValidationService
from app.models.document import Document, DocumentStatus
from app.models.extraction import Extraction
from app.models.review import Review
from app.models.validation import Validation
from app.plugins.invoice.confidence import (
    CRITICAL_FIELDS,
    FIELD_WEIGHTS,
    build_field_scores,
)
from app.plugins.invoice.prompt import INVOICE_SYSTEM_PROMPT, build_invoice_prompt
from app.plugins.invoice.schema import InvoiceData
from app.schemas.review import ReviewDecision
from app.schemas.validation import Severity, ValidationReport
from app.workers.celery_app import celery_app

log = structlog.get_logger()


class InvoiceReprocessor:
    """Re-runs extraction -> confidence -> validation with the agent's hint.

    This is what makes RETRY a real decision rather than dead code: the agent's
    retry_hint is appended to the extraction prompt, so attempt 2 has guidance
    attempt 1 lacked ("the vendor is the company at the top, not 'Bill To'").

    Keeps the latest result so the caller can persist an improved extraction.
    """

    def __init__(
        self,
        *,
        provider: LLMProvider,
        clean_text: str,
        db: Session,
        document_id: str,
        settings: Settings,
    ) -> None:
        self._provider = provider
        self._clean_text = clean_text
        self._db = db
        self._document_id = document_id
        self._settings = settings
        self.latest: tuple[StructuredExtractionResult, dict, ValidationReport] | None = None

    def run(self, hint: str | None = None) -> tuple[StructuredExtractionResult, dict, ValidationReport]:
        prompt = build_invoice_prompt(self._clean_text)
        if hint:
            prompt += (
                "\n=== REVIEW GUIDANCE (a previous attempt was incomplete) ===\n"
                f"{hint}\n"
            )

        structured = StructuredExtractor(self._provider, max_retries=1).extract(
            document_text=self._clean_text,
            system_prompt=INVOICE_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema_model=InvoiceData,
        )

        report = ConfidenceService(self._settings.confidence_strategy).build_report(
            scores=build_field_scores(structured.data, self._clean_text),
            weights=FIELD_WEIGHTS,
            critical=CRITICAL_FIELDS,
        )

        val_report = ValidationService(invoice_rule_config()).validate(
            ValidationContext(
                data=structured.data,
                source_text=self._clean_text,
                document_id=self._document_id,
                duplicate_lookup=SqlDuplicateLookup(self._db),
                vendor_directory=load_vendor_directory(self._settings.vendor_directory_path),
            )
        )

        self.latest = (structured, report.model_dump(mode="json"), val_report)
        return structured, report.model_dump(mode="json"), val_report

    def reprocess(self, *, hint: str | None) -> tuple[dict, dict, ValidationReport]:
        """The Reprocessor port the ReviewAgent depends on."""
        structured, confidence, val_report = self.run(hint)
        return structured.data, confidence, val_report


def _persist_extraction(
    db: Session,
    doc: Document,
    *,
    method: str,
    structured: StructuredExtractionResult,
    confidence: dict,
) -> None:
    row = db.query(Extraction).filter_by(document_id=doc.id).one_or_none()
    if row is None:
        row = Extraction(document_id=doc.id)
        db.add(row)
    row.extraction_method = method
    row.model = structured.model
    row.data = structured.data
    row.parse_error = structured.parse_error
    row.overall_confidence = confidence["overall"]
    row.confidence = confidence


def _persist_validation(db: Session, doc: Document, val_report: ValidationReport) -> None:
    row = db.query(Validation).filter_by(document_id=doc.id).one_or_none()
    if row is None:
        row = Validation(document_id=doc.id)
        db.add(row)
    row.overall = val_report.overall.value
    row.report = val_report.model_dump(mode="json")


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

            # Idempotency/resume guard: if already terminal, don't redo the work.
            if doc.status in (
                DocumentStatus.COMPLETED,
                DocumentStatus.ESCALATED,
                DocumentStatus.REJECTED,
            ):
                log.info("pipeline.already_done", document_id=document_id, status=doc.status.value)
                return {"status": doc.status.value}

            doc.status = DocumentStatus.PROCESSING
            db.flush()

            data = get_storage(settings).load(doc.storage_key)

            # --- Stage 1: text extraction (native/OCR decision) ---
            text_result = ExtractionService(NativeExtractor(), OcrExtractor()).extract(
                data, doc.content_type
            )
            # Strip PDF column padding before the LLM sees it: deterministic
            # cleanup removes noise far more cheaply than prompting around it.
            clean_text = normalize_text(text_result.full_text)

            provider = OllamaProvider(settings.ollama_base_url, settings.ollama_model)
            reprocessor = InvoiceReprocessor(
                provider=provider,
                clean_text=clean_text,
                db=db,
                document_id=str(doc.id),
                settings=settings,
            )

            # --- Stages 2-4: structured extraction -> confidence -> validation ---
            structured, confidence, val_report = reprocessor.run()

            _persist_extraction(
                db, doc, method=text_result.method.value, structured=structured, confidence=confidence
            )
            _persist_validation(db, doc, val_report)

            log.info(
                "pipeline.extracted",
                document_id=document_id,
                method=text_result.method.value,
                parse_error=structured.parse_error,
                confidence=confidence["overall"],
                strategy=confidence["strategy"],
            )
            log.info(
                "pipeline.validated",
                document_id=document_id,
                validation=val_report.overall.value,
                counts=val_report.counts,
                failures=[r.rule_id for r in val_report.failures],
            )

            # --- Stage 5: agentic review (only when there is something to review) ---
            needs_review = (
                confidence["overall"] < settings.confidence_threshold
                or val_report.overall is not Severity.PASS
            )
            if not needs_review:
                doc.status = DocumentStatus.COMPLETED
                log.info("pipeline.completed", document_id=document_id, review="skipped")
                return {
                    "status": doc.status.value,
                    "confidence": confidence["overall"],
                    "validation": val_report.overall.value,
                    "review": None,
                }

            doc.status = DocumentStatus.REVIEW
            db.flush()

            outcome = ReviewAgent(
                provider, reprocessor=reprocessor, max_attempts=settings.review_max_attempts
            ).review(
                document_id=str(doc.id),
                data=structured.data,
                confidence=confidence,
                validation=val_report,
            )

            # A retry may have produced a better extraction — persist the latest.
            if outcome.attempts > 1 and reprocessor.latest is not None:
                new_structured, new_confidence, new_val = reprocessor.latest
                _persist_extraction(
                    db, doc, method=text_result.method.value,
                    structured=new_structured, confidence=new_confidence,
                )
                _persist_validation(db, doc, new_val)
                log.info(
                    "pipeline.extraction_updated_after_retry",
                    document_id=document_id,
                    confidence=new_confidence["overall"],
                    validation=new_val.overall.value,
                )

            rev = db.query(Review).filter_by(document_id=doc.id).one_or_none()
            if rev is None:
                rev = Review(document_id=doc.id)
                db.add(rev)
            rev.decision = outcome.decision.value
            rev.reasoning = outcome.reasoning
            rev.attempts = outcome.attempts
            rev.overridden = outcome.overridden
            rev.override_reason = outcome.override_reason
            rev.history = outcome.history

            doc.status = {
                ReviewDecision.ACCEPT: DocumentStatus.COMPLETED,
                ReviewDecision.ESCALATE: DocumentStatus.ESCALATED,
                ReviewDecision.REJECT: DocumentStatus.REJECTED,
                ReviewDecision.RETRY: DocumentStatus.ESCALATED,  # unreachable: guarded
            }[outcome.decision]

            log.info(
                "pipeline.reviewed",
                document_id=document_id,
                decision=outcome.decision.value,
                overridden=outcome.overridden,
                override_reason=outcome.override_reason,
                attempts=outcome.attempts,
                status=doc.status.value,
            )
            return {
                "status": doc.status.value,
                "confidence": confidence["overall"],
                "validation": val_report.overall.value,
                "review": outcome.decision.value,
            }

    except SoftTimeLimitExceeded:
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
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            _mark_failed(document_id, f"max retries exceeded: {exc}")
            return {"status": "failed"}


def _mark_failed(document_id: str, reason: str) -> None:
    """Terminal failure: document -> FAILED with reason. Never left in PROCESSING."""
    with session_scope() as db:
        doc = db.get(Document, document_id)
        if doc is not None:
            doc.status = DocumentStatus.FAILED
            doc.doc_metadata = {**(doc.doc_metadata or {}), "failure_reason": reason}
    log.error("pipeline.failed", document_id=document_id, reason=reason)
