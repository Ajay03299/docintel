import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class SourceChannel(str, Enum):
    REST_UPLOAD = "rest_upload"
    EMAIL = "email"
    BATCH = "batch"
    CLOUD = "cloud"


class DocumentEnvelope(BaseModel):
    document_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    source_channel: SourceChannel
    original_filename: str
    content_type: str
    size_bytes: int
    storage_key: str
    checksum_sha256: str
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = Field(default_factory=dict)