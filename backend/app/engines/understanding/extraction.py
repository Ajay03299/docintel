from abc import ABC, abstractmethod

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

from app.schemas.extraction import (
    ExtractionMethod,
    PageText,
    TextExtractionResult,
)


class TextExtractor(ABC):
    @abstractmethod
    def extract(self, data: bytes, content_type: str) -> TextExtractionResult: ...


class NativeExtractor(TextExtractor):
    """PyMuPDF text-layer extraction. Instant and perfect for digital PDFs;
    returns near-empty text for scanned/image PDFs."""

    def extract(self, data: bytes, content_type: str) -> TextExtractionResult:
        pages: list[PageText] = []
        with fitz.open(stream=data, filetype="pdf") as doc:
            for i, page in enumerate(doc):
                text = page.get_text().strip()
                pages.append(PageText(page_number=i + 1, text=text, char_count=len(text)))
        total = sum(p.char_count for p in pages)
        return TextExtractionResult(
            method=ExtractionMethod.NATIVE,
            pages=pages,
            total_chars=total,
            page_count=len(pages),
        )


class OcrExtractor(TextExtractor):
    """Tesseract OCR over rasterized pages. Slower; used only when native
    extraction is insufficient. Handles both scanned PDFs and images."""

    def __init__(self, dpi: int = 200) -> None:
        self._dpi = dpi

    def extract(self, data: bytes, content_type: str) -> TextExtractionResult:
        pages: list[PageText] = []
        if content_type == "application/pdf":
            with fitz.open(stream=data, filetype="pdf") as doc:
                for i, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=self._dpi)
                    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    text = pytesseract.image_to_string(img).strip()
                    pages.append(PageText(page_number=i + 1, text=text, char_count=len(text)))
        else:  # image/png, image/jpeg
            import io
            img = Image.open(io.BytesIO(data))
            text = pytesseract.image_to_string(img).strip()
            pages.append(PageText(page_number=1, text=text, char_count=len(text)))
        total = sum(p.char_count for p in pages)
        return TextExtractionResult(
            method=ExtractionMethod.OCR,
            pages=pages,
            total_chars=total,
            page_count=len(pages),
        )
    
    class ExtractionService:

        def __init__(
        self,
        native: TextExtractor,
        ocr: TextExtractor,
        min_chars_per_page: int = 50,
        ) -> None:
            self._native = native
            self._ocr = ocr
            self._min_chars_per_page = min_chars_per_page

        def extract(self, data: bytes, content_type: str) -> TextExtractionResult:
            # Images have no text layer at all → OCR directly.
            if content_type in ("image/png", "image/jpeg"):
                result = self._ocr.extract(data, content_type)
                result.ocr_fallback_reason = "input is an image; no text layer possible"
                return result

            native = self._native.extract(data, content_type)
            if self._is_sufficient(native):
                return native

            # Native text too sparse → the PDF is almost certainly a scan.
            reason = (
                f"native extraction yielded {native.total_chars} chars over "
                f"{native.page_count} page(s), below threshold of "
                f"{self._min_chars_per_page}/page"
            )
            ocr = self._ocr.extract(data, content_type)
            ocr.ocr_fallback_reason = reason
            return ocr

        def _is_sufficient(self, result: TextExtractionResult) -> bool:
            if result.page_count == 0:
                return False
            avg = result.total_chars / result.page_count
            return avg >= self._min_chars_per_page

class ExtractionService:
    """Deterministic-first extraction: try the cheap native path, fall back to
    OCR only when the text layer is too sparse to be a real digital document.

    The threshold is injected, not hardcoded — different document types or
    quality tiers can tune it without touching this logic (open/closed)."""

    def __init__(
        self,
        native: TextExtractor,
        ocr: TextExtractor,
        min_chars_per_page: int = 50,
    ) -> None:
        self._native = native
        self._ocr = ocr
        self._min_chars_per_page = min_chars_per_page

    def extract(self, data: bytes, content_type: str) -> TextExtractionResult:
        # Images have no text layer at all → OCR directly.
        if content_type in ("image/png", "image/jpeg"):
            result = self._ocr.extract(data, content_type)
            result.ocr_fallback_reason = "input is an image; no text layer possible"
            return result

        native = self._native.extract(data, content_type)
        if self._is_sufficient(native):
            return native

        # Native text too sparse → the PDF is almost certainly a scan.
        reason = (
            f"native extraction yielded {native.total_chars} chars over "
            f"{native.page_count} page(s), below threshold of "
            f"{self._min_chars_per_page}/page"
        )
        ocr = self._ocr.extract(data, content_type)
        ocr.ocr_fallback_reason = reason
        return ocr

    def _is_sufficient(self, result: TextExtractionResult) -> bool:
        if result.page_count == 0:
            return False
        avg = result.total_chars / result.page_count
        return avg >= self._min_chars_per_page


def normalize_text(text: str) -> str:
    """Collapse layout padding before sending text to an LLM.

    PDF text layers are often column-padded with runs of spaces, which is pure
    noise to a language model and wastes context. Deterministic cleanup is far
    cheaper and more reliable than asking the model to look past it.
    """
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)
