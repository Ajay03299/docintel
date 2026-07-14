import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.document import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), index=True, unique=True
    )
    extraction_method: Mapped[str] = mapped_column(String(16))  # native | ocr
    model: Mapped[str] = mapped_column(String(64))
    data: Mapped[dict] = mapped_column(JSONB, default=dict)          # the structured invoice JSON
    parse_error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)