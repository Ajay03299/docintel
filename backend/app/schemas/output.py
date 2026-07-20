from pydantic import BaseModel, Field


class ExportRequest(BaseModel):
    format: str = Field(description="Registered exporter id, e.g. 'json', 'csv'.")
    options: dict = Field(default_factory=dict)


class ExportResult(BaseModel):
    format: str
    filename: str
    media_type: str
    size_bytes: int
