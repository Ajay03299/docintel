from app.engines.understanding.structured_extraction import StructuredExtractor
from app.plugins.invoice.schema import InvoiceData
from app.schemas.llm import LLMResponse


class FakeProvider:
    name = "fake"
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0
    def complete(self, *, system, prompt, json_schema=None):
        self.calls += 1
        return LLMResponse(text=self._responses.pop(0), model="fake", latency_ms=1.0)


def test_clean_json_extracts():
    p = FakeProvider(['{"invoice_number": "INV-1", "total": 100.0}'])
    out = StructuredExtractor(p).extract(
        document_text="x", system_prompt="s", user_prompt="u", schema_model=InvoiceData,
    )
    assert out.data["invoice_number"] == "INV-1"
    assert out.parse_error is None
    assert p.calls == 1


def test_json_fence_is_stripped():
    p = FakeProvider(['```json\n{"invoice_number": "INV-2"}\n```'])
    out = StructuredExtractor(p).extract(
        document_text="x", system_prompt="s", user_prompt="u", schema_model=InvoiceData,
    )
    assert out.data["invoice_number"] == "INV-2"


def test_malformed_then_retry_succeeds():
    p = FakeProvider(['not json at all', '{"invoice_number": "INV-3"}'])
    out = StructuredExtractor(p, max_retries=1).extract(
        document_text="x", system_prompt="s", user_prompt="u", schema_model=InvoiceData,
    )
    assert out.data["invoice_number"] == "INV-3"
    assert out.parse_attempts == 2
    assert p.calls == 2  # retried once


def test_exhausted_retries_returns_empty_not_raises():
    p = FakeProvider(['garbage', 'still garbage'])
    out = StructuredExtractor(p, max_retries=1).extract(
        document_text="x", system_prompt="s", user_prompt="u", schema_model=InvoiceData,
    )
    assert out.data == {}
    assert out.parse_error is not None   # error recorded, nothing raised