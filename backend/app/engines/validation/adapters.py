"""Concrete adapters for the validation ports.

Rules depend on the DuplicateLookup / VendorDirectory Protocols, never on these
classes — which is why every rule unit test runs with fakes and no database.
"""

from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.extraction import Extraction


class SqlDuplicateLookup:
    """Finds prior documents with the same vendor + invoice number.

    Deliberately deterministic (exact match on a normalized key) rather than
    embedding-based similarity: a finance team must be able to see WHY two
    invoices were flagged as duplicates. Explainability beats recall here.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def find_duplicates(
        self,
        *,
        vendor_name: str | None,
        invoice_number: str | None,
        total: float | None,
        exclude_document_id: str | None,
    ) -> list[str]:
        if not vendor_name or not invoice_number:
            return []

        # Compare on normalized JSONB values so 'ACME Ltd' == '  acme ltd  '.
        vendor_expr = func.lower(func.trim(Extraction.data["vendor_name"].astext))
        number_expr = func.lower(func.trim(Extraction.data["invoice_number"].astext))

        stmt = (
            select(Extraction.document_id)
            .where(vendor_expr == vendor_name.strip().lower())
            .where(number_expr == invoice_number.strip().lower())
        )
        if exclude_document_id:
            stmt = stmt.where(Extraction.document_id != exclude_document_id)

        return [str(row[0]) for row in self._db.execute(stmt).all()]


class StaticVendorDirectory:
    """Vendor master data. A static list stands in for what would be an ERP
    lookup in production; the port means swapping it changes no rule code."""

    def __init__(self, vendors: Iterable[str]) -> None:
        self._vendors = {v.strip().lower() for v in vendors}

    def is_known(self, vendor_name: str) -> bool:
        return vendor_name.strip().lower() in self._vendors


def load_vendor_directory(path: str | None) -> StaticVendorDirectory | None:
    """Load vendors from a newline-delimited file; None if not configured."""
    if not path:
        return None
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        return None
    names = [line.strip() for line in p.read_text().splitlines() if line.strip()]
    return StaticVendorDirectory(names)
