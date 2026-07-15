from app.engines.confidence.signals import (
    is_iso_currency,
    is_present,
    parses_as_date,
    score_field,
)
from app.schemas.confidence import FieldScore

# Relative importance. Tunable without touching engine code.
FIELD_WEIGHTS: dict[str, float] = {
    "invoice_number": 0.20,
    "invoice_date": 0.15,
    "vendor_name": 0.15,
    "currency": 0.05,
    "subtotal": 0.10,
    "tax_amount": 0.10,
    "total": 0.20,
    "line_items": 0.05,
}

# If ANY of these is weak, the whole document is untrustworthy.
CRITICAL_FIELDS: set[str] = {"invoice_number", "vendor_name", "total"}

_TOLERANCE = 0.01


def _score_line_items(items: list | None, source_text: str | None) -> FieldScore:
    if not is_present(items):
        return FieldScore(field="line_items", value=items, confidence=0.0, signals=["absent"])
    total_n = len(items)
    with_amount = sum(1 for i in items if i.get("amount") is not None)
    ratio = with_amount / total_n if total_n else 0.0
    return FieldScore(
        field="line_items",
        value=f"{total_n} item(s)",
        confidence=round(min(1.0, 0.4 + 0.6 * ratio), 4),
        signals=[f"count={total_n}", f"with_amount={with_amount}/{total_n}(ratio={ratio:.2f})"],
    )


def _apply_arithmetic_coherence(scores: list[FieldScore], data: dict) -> None:
    """subtotal + tax - discount == total is evidence the numeric cluster was
    read correctly. Note: Engine 3 will check this same identity as a business
    RULE (PASS/FAIL + suggested fix). Here it is only a confidence SIGNAL —
    same arithmetic, different consumer: trust vs. correctness."""
    subtotal, tax = data.get("subtotal"), data.get("tax_amount")
    discount, total = data.get("discount") or 0.0, data.get("total")
    if not all(isinstance(v, (int, float)) for v in (subtotal, tax, total)):
        return

    expected = subtotal + tax - discount
    coherent = abs(expected - total) <= _TOLERANCE
    for s in scores:
        if s.field not in ("subtotal", "tax_amount", "total"):
            continue
        if coherent:
            s.confidence = round(min(1.0, s.confidence + 0.10), 4)
            s.signals.append("arithmetic_coherent(+0.10)")
        else:
            s.confidence = round(s.confidence * 0.5, 4)
            s.signals.append(f"arithmetic_mismatch(x0.5): expected {expected:.2f}, got {total:.2f}")


def build_field_scores(data: dict, source_text: str | None) -> list[FieldScore]:
    scores = [
        score_field("invoice_number", data.get("invoice_number"), source_text),
        score_field("invoice_date", data.get("invoice_date"), source_text, parses_as_date),
        score_field("vendor_name", data.get("vendor_name"), source_text),
        score_field("currency", data.get("currency"), source_text, is_iso_currency),
        score_field("subtotal", data.get("subtotal"), source_text),
        score_field("tax_amount", data.get("tax_amount"), source_text),
        score_field("total", data.get("total"), source_text),
        _score_line_items(data.get("line_items"), source_text),
    ]
    _apply_arithmetic_coherence(scores, data)
    return scores