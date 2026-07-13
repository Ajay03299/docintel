from enum import Enum

from pydantic import BaseModel, Field


class ExtractionMethod(str, Enum):
    NATIVE = "native"   # PyMuPDF text layer
    OCR = "ocr"         # Tesseract on rasterized pages


class PageText(BaseModel):
    page_number: int
    text: str
    char_count: int


class TextExtractionResult(BaseModel):
    method: ExtractionMethod
    pages: list[PageText]
    total_chars: int
    page_count: int
    ocr_fallback_reason: str | None = Field(
        default=None,
        description="Why OCR was triggered; None if native extraction sufficed.",
    )

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)