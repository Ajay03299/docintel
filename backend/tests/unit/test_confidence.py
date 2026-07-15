from app.engines.confidence.service import ConfidenceService
from app.engines.confidence.signals import score_field
from app.engines.confidence.strategies import (
    MinGatedWeightedMean,
    WeightedArithmeticMean,
    WeightedGeometricMean,
)
from app.plugins.invoice.confidence import (
    CRITICAL_FIELDS,
    FIELD_WEIGHTS,
    build_field_scores,
)
from app.schemas.confidence import FieldScore

SRC = "ACME SUPPLIES LTD\nInvoice Number: INV-1\nDate: 2026-03-15\nTotal: 118.00\nUSD"


def _scores(**kv) -> list[FieldScore]:
    return [FieldScore(field=k, value=None, confidence=v) for k, v in kv.items()]


def test_absent_field_scores_zero():
    s = score_field("vendor_name", None, SRC)
    assert s.confidence == 0.0
    assert "absent" in s.signals


def test_grounded_value_scores_higher_than_hallucinated():
    real = score_field("vendor_name", "ACME SUPPLIES LTD", SRC)
    fake = score_field("vendor_name", "GLOBEX CORP", SRC)
    assert real.confidence > fake.confidence
    assert any("grounded" in x for x in real.signals)
    assert any("not_found_in_source" in x for x in fake.signals)


def test_arithmetic_mean_is_too_forgiving_on_missing_total():
    """Documents WHY min_gated is the default: a null total still scores ~0.70."""
    scores = _scores(invoice_number=1.0, invoice_date=1.0, vendor_name=1.0,
                     currency=1.0, subtotal=1.0, tax_amount=1.0, total=0.0, line_items=1.0)
    out = WeightedArithmeticMean().aggregate(scores, FIELD_WEIGHTS, CRITICAL_FIELDS)
    assert 0.65 < out < 0.85


def test_min_gated_caps_score_at_weakest_critical_field():
    scores = _scores(invoice_number=1.0, invoice_date=1.0, vendor_name=1.0,
                     currency=1.0, subtotal=1.0, tax_amount=1.0, total=0.0, line_items=1.0)
    out = MinGatedWeightedMean().aggregate(scores, FIELD_WEIGHTS, CRITICAL_FIELDS)
    assert out == 0.0


def test_non_critical_zero_does_not_tank_min_gated():
    """currency is NOT critical, so a zero there must not collapse the score."""
    scores = _scores(invoice_number=1.0, invoice_date=1.0, vendor_name=1.0,
                     currency=0.0, subtotal=1.0, tax_amount=1.0, total=1.0, line_items=1.0)
    out = MinGatedWeightedMean().aggregate(scores, FIELD_WEIGHTS, CRITICAL_FIELDS)
    assert out > 0.90


def test_geometric_mean_punishes_any_zero():
    scores = _scores(invoice_number=1.0, invoice_date=1.0, vendor_name=1.0,
                     currency=0.0, subtotal=1.0, tax_amount=1.0, total=1.0, line_items=1.0)
    out = WeightedGeometricMean().aggregate(scores, FIELD_WEIGHTS, CRITICAL_FIELDS)
    assert out < 0.60


def test_arithmetic_mismatch_lowers_numeric_confidence():
    good = build_field_scores(
        {"subtotal": 100.0, "tax_amount": 18.0, "discount": None, "total": 118.0}, SRC)
    bad = build_field_scores(
        {"subtotal": 100.0, "tax_amount": 18.0, "discount": None, "total": 999.0}, SRC)
    g = next(s for s in good if s.field == "total")
    b = next(s for s in bad if s.field == "total")
    assert g.confidence > b.confidence
    assert any("arithmetic_mismatch" in x for x in b.signals)


def test_all_null_extraction_scores_zero_end_to_end():
    """The lecture-PDF case: invoice extractor on a non-invoice must NOT pass."""
    scores = build_field_scores({}, "Carnegie Mellon Transactions lecture notes")
    report = ConfidenceService("min_gated").build_report(
        scores=scores, weights=FIELD_WEIGHTS, critical=CRITICAL_FIELDS)
    assert report.overall == 0.0
