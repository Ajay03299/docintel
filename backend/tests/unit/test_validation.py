from datetime import datetime


from app.engines.validation.base import ValidationContext
from app.engines.validation.config import invoice_rule_config
from app.engines.validation.registry import get_rules
from app.engines.validation.service import ValidationService
from app.schemas.validation import Severity

NOW = datetime(2026, 6, 1)

GOOD = {
    "invoice_number": "INV-2026-0042",
    "invoice_date": "2026-03-15",
    "vendor_name": "ACME SUPPLIES LTD",
    "vendor_tax_id": None,
    "currency": "USD",
    "subtotal": 100.0,
    "tax_amount": 18.0,
    "discount": None,
    "total": 118.0,
    "line_items": [
        {"description": "Widget A", "quantity": 10.0, "unit_price": 5.0, "amount": 50.0},
        {"description": "Widget B", "quantity": 4.0, "unit_price": 12.5, "amount": 50.0},
    ],
}


class FakeDuplicates:
    def __init__(self, matches=None):
        self._matches = matches or []
    def find_duplicates(self, **kw):
        return self._matches


class FakeVendors:
    def __init__(self, known=()):
        self._known = {v.lower() for v in known}
    def is_known(self, vendor_name):
        return vendor_name.lower() in self._known


def _ctx(**overrides):
    data = {**GOOD, **overrides.pop("data", {})}
    return ValidationContext(data=data, now=NOW, document_id="doc-1", **overrides)


def _run(ctx):
    return ValidationService(invoice_rule_config()).validate(ctx)


def _result(report, rule_id):
    return next(r for r in report.results if r.rule_id == rule_id)


def test_all_rules_are_registered():
    """Autoloader must find every rule module without an explicit import list."""
    assert len(get_rules()) >= 17


def test_clean_invoice_passes():
    report = _run(_ctx())
    assert report.overall is Severity.PASS
    assert not report.failures


def test_broken_total_fails_with_actionable_fix():
    report = _run(_ctx(data={"total": 999.0}))
    r = _result(report, "invoice_total_arithmetic")
    assert r.severity is Severity.FAIL
    assert "118.00" in r.suggested_fix          # tells the reviewer the right value
    assert report.overall is Severity.FAIL


def test_missing_mandatory_field_fails():
    report = _run(_ctx(data={"vendor_name": None}))
    assert _result(report, "mandatory_fields").severity is Severity.FAIL


def test_future_date_fails():
    report = _run(_ctx(data={"invoice_date": "2026-12-25"}))   # NOW is 2026-06-01
    r = _result(report, "future_date")
    assert r.severity is Severity.FAIL
    assert "future" in r.reason.lower()


def test_stale_date_warns_not_fails():
    report = _run(_ctx(data={"invoice_date": "2024-01-01"}))
    assert _result(report, "stale_date").severity is Severity.WARNING


def test_absurd_tax_rate_fails():
    report = _run(_ctx(data={"tax_amount": 400.0, "total": 500.0}))
    assert _result(report, "tax_percentage_plausible").severity is Severity.FAIL


def test_negative_quantity_fails():
    items = [{"description": "W", "quantity": -5.0, "unit_price": 5.0, "amount": -25.0}]
    report = _run(_ctx(data={"line_items": items}))
    assert _result(report, "negative_quantity").severity is Severity.FAIL


def test_line_item_math_mismatch_fails():
    items = [{"description": "W", "quantity": 10.0, "unit_price": 5.0, "amount": 99.0}]
    report = _run(_ctx(data={"line_items": items, "subtotal": 99.0, "total": 117.0}))
    assert _result(report, "line_item_amount_consistency").severity is Severity.FAIL


def test_duplicate_invoice_detected_via_injected_lookup():
    report = _run(_ctx(duplicate_lookup=FakeDuplicates(["doc-99"])))
    r = _result(report, "duplicate_invoice")
    assert r.severity is Severity.FAIL
    assert "doc-99" in r.reason


def test_duplicate_rule_skips_when_no_lookup_configured():
    """A rule that cannot run must report SKIPPED, never PASS."""
    assert _result(_run(_ctx()), "duplicate_invoice").severity is Severity.SKIPPED


def test_unknown_vendor_is_downgraded_to_warning_by_config():
    """vendor_known emits WARNING and YAML confirms it — policy lives in config."""
    report = _run(_ctx(vendor_directory=FakeVendors(["Globex"])))
    assert _result(report, "vendor_known").severity is Severity.WARNING
    assert report.overall is Severity.WARNING


def test_known_vendor_passes():
    report = _run(_ctx(vendor_directory=FakeVendors(["ACME SUPPLIES LTD"])))
    assert _result(report, "vendor_known").severity is Severity.PASS


def test_duplicate_line_items_warn():
    item = {"description": "Widget A", "quantity": 10.0, "unit_price": 5.0, "amount": 50.0}
    report = _run(_ctx(data={"line_items": [item, dict(item)], "subtotal": 100.0}))
    assert _result(report, "duplicate_line_items").severity is Severity.WARNING


def test_bad_currency_fails():
    assert _result(_run(_ctx(data={"currency": "$"})), "currency_valid").severity is Severity.FAIL


def test_disabled_rule_does_not_run():
    cfg = {**invoice_rule_config(), "future_date": {"enabled": False}}
    report = ValidationService(cfg).validate(_ctx(data={"invoice_date": "2026-12-25"}))
    assert all(r.rule_id != "future_date" for r in report.results)


def test_buggy_rule_is_isolated_not_fatal():
    """One broken rule must not take down validation for the whole document."""
    from app.engines.validation.base import ValidationRule

    class Exploding(ValidationRule):
        rule_id = "exploding"
        def evaluate(self, ctx):
            raise RuntimeError("boom")

    svc = ValidationService({"exploding": {"enabled": True}}, rules={"exploding": Exploding})
    report = svc.validate(_ctx())
    r = _result(report, "exploding")
    assert r.severity is Severity.SKIPPED
    assert "boom" in r.reason


def test_empty_extraction_fails_mandatory_not_crashes():
    """The lecture-PDF case: all-null data must fail cleanly, never raise."""
    report = ValidationService(invoice_rule_config()).validate(
        ValidationContext(data={}, now=NOW)
    )
    assert report.overall is Severity.FAIL
    assert _result(report, "mandatory_fields").severity is Severity.FAIL
