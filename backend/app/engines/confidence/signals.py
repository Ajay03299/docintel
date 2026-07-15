import re
from datetime import datetime
from typing import Any, Callable

from app.schemas.confidence import FieldScore

_ISO_CURRENCY = re.compile(r"^[A-Z]{3}$")
_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y")


def is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, (list, dict)) and len(value) == 0:
        return False
    return True


def is_grounded(value: Any, source_text: str | None) -> bool:
    """Anti-hallucination check: does the value actually appear in the document?
    A value the model invented cannot be found in the source text."""
    if not source_text or not is_present(value):
        return False
    hay = source_text.lower()
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        candidates = {f"{value:g}", f"{float(value):.2f}"}
        if float(value).is_integer():
            candidates.add(str(int(value)))
        return any(c in hay for c in candidates)
    return str(value).strip().lower() in hay


def parses_as_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    for fmt in _DATE_FORMATS:
        try:
            datetime.strptime(value.strip(), fmt)
            return True
        except ValueError:
            continue
    return False


def is_iso_currency(value: Any) -> bool:
    return isinstance(value, str) and bool(_ISO_CURRENCY.match(value.strip().upper()))


def score_field(
    field: str,
    value: Any,
    source_text: str | None,
    format_check: Callable[[Any], bool] | None = None,
) -> FieldScore:
    """Evidence-based field confidence. Weights are deliberately explicit so any
    score can be explained field-by-field:
        absent                -> 0.00
        present               -> 0.50 (model asserted it; small models over-report)
        + grounded in source  -> +0.30 (value provably appears in the document)
        + format valid        -> +0.20 (parses as the expected type)
        + format invalid      -> -0.20
    """
    if not is_present(value):
        return FieldScore(field=field, value=value, confidence=0.0, signals=["absent"])

    conf = 0.5
    signals = ["present(+0.50)"]

    if is_grounded(value, source_text):
        conf += 0.30
        signals.append("grounded_in_source(+0.30)")
    else:
        signals.append("not_found_in_source(+0.00)")

    if format_check is None:
        conf += 0.20
        signals.append("no_format_rule(+0.20)")
    elif format_check(value):
        conf += 0.20
        signals.append("format_valid(+0.20)")
    else:
        conf -= 0.20
        signals.append("format_invalid(-0.20)")

    return FieldScore(
        field=field, value=value, confidence=max(0.0, min(1.0, conf)), signals=signals
    )