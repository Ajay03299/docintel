from app.engines.understanding.extraction import ExtractionService
from app.schemas.extraction import (
    ExtractionMethod,
    PageText,
    TextExtractionResult,
)


def _result(method, per_page_chars, pages=1):
    page_list = [
        PageText(page_number=i + 1, text="x" * per_page_chars, char_count=per_page_chars)
        for i in range(pages)
    ]
    return TextExtractionResult(
        method=method,
        pages=page_list,
        total_chars=per_page_chars * pages,
        page_count=pages,
    )


class FakeExtractor:
    def __init__(self, result):
        self._result = result
        self.called = False

    def extract(self, data, content_type):
        self.called = True
        return self._result


def test_uses_native_when_text_is_rich():
    native = FakeExtractor(_result(ExtractionMethod.NATIVE, per_page_chars=500))
    ocr = FakeExtractor(_result(ExtractionMethod.OCR, per_page_chars=500))
    svc = ExtractionService(native=native, ocr=ocr, min_chars_per_page=50)

    out = svc.extract(b"%PDF-...", "application/pdf")

    assert out.method == ExtractionMethod.NATIVE
    assert ocr.called is False   # OCR must NOT run for a digital PDF — cost discipline
    assert out.ocr_fallback_reason is None


def test_falls_back_to_ocr_when_text_is_sparse():
    native = FakeExtractor(_result(ExtractionMethod.NATIVE, per_page_chars=5))  # scan-like
    ocr = FakeExtractor(_result(ExtractionMethod.OCR, per_page_chars=800))
    svc = ExtractionService(native=native, ocr=ocr, min_chars_per_page=50)

    out = svc.extract(b"%PDF-...", "application/pdf")

    assert out.method == ExtractionMethod.OCR
    assert ocr.called is True
    assert "below threshold" in out.ocr_fallback_reason


def test_images_go_straight_to_ocr():
    native = FakeExtractor(_result(ExtractionMethod.NATIVE, per_page_chars=500))
    ocr = FakeExtractor(_result(ExtractionMethod.OCR, per_page_chars=300))
    svc = ExtractionService(native=native, ocr=ocr, min_chars_per_page=50)

    out = svc.extract(b"\x89PNG...", "image/png")

    assert out.method == ExtractionMethod.OCR
    assert native.called is False   # no text layer on an image; don't waste the call
    assert "image" in out.ocr_fallback_reason

def test_normalize_text_collapses_column_padding():
    """PDF text layers pad columns with runs of spaces; ~80% of a real invoice's
    extracted chars were padding, which measurably degraded LLM extraction."""
    from app.engines.understanding.extraction import normalize_text

    raw = "ACME SUPPLIES LTD" + " " * 60 + "\n" + " " * 80 + "\nTotal: 118.00" + " " * 40
    out = normalize_text(raw)

    assert out == "ACME SUPPLIES LTD\nTotal: 118.00"
    assert len(out) < len(raw) / 4          # padding dominated the raw text
    assert "ACME SUPPLIES LTD" in out       # content preserved
