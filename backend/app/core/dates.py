"""Shared date parsing. Both the confidence engine (is this a valid date?) and
the validation engine (is this date in the future?) need identical parsing —
duplicating the format list in two engines would guarantee they drift apart.
"""

from datetime import datetime

DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
)


def parse_date(value: object) -> datetime | None:
    """Return a datetime if the value parses in any known format, else None."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None
