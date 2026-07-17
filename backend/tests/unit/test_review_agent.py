import json

from app.engines.review.agent import ReviewAgent
from app.engines.review.retryability import classify_failures
from app.schemas.llm import LLMResponse
from app.schemas.review import ReviewDecision
from app.schemas.validation import Severity, ValidationReport, ValidationResult

GROUNDED = ["present(+0.50)", "grounded_in_source(+0.30)", "no_format_rule(+0.20)"]


def _conf(overall=1.0, **fields):
    return {
        "overall": overall,
        "strategy": "min_gated",
        "fields": [
            {"field": k, "value": v[0], "confidence": v[1], "signals": v[2]}
            for k, v in fields.items()
        ],
        "critical_fields": ["invoice_number", "vendor_name", "total"],
    }


def _report(*results):
    sev = max((r.severity for r in results), key=lambda s: ["pass", "skipped", "warning", "fail"].index(s.value), default=Severity.PASS)
    return ValidationReport(overall=sev, results=list(results), counts={})


def _fail(rule_id, fields):
    return ValidationResult(rule_id=rule_id, severity=Severity.FAIL, reason="x", fields=fields)


class FakeProvider:
    name = "fake"
    def __init__(self, *decisions):
        self._d = list(decisions)
        self.calls = 0
    def complete(self, *, system, prompt, json_schema=None):
        self.calls += 1
        d = self._d.pop(0) if self._d else self._d[-1]
        return LLMResponse(text=json.dumps(d), model="fake", latency_ms=1.0)


class FakeReprocessor:
    def __init__(self, results):
        self._results = list(results)
        self.calls = 0
    def reprocess(self, *, hint):
        self.calls += 1
        return self._results.pop(0)


# ---------- retryability analysis ----------

def test_grounded_arithmetic_failure_is_blocking_not_retryable():
    """The real broken-invoice case: total=999 IS in the document. Re-reading it
    yields 999 again, so the retry is pointless even though the RULE is retryable."""
    report = _report(_fail("invoice_total_arithmetic", ["subtotal", "tax_amount", "total"]))
    conf = _conf(0.5, subtotal=(100.0, 1.0, GROUNDED), tax_amount=(18.0, 1.0, GROUNDED),
                 total=(999.0, 0.5, GROUNDED))
    retryable, blocking, why = classify_failures(report, conf)
    assert retryable == []
    assert "invoice_total_arithmetic" in blocking
    assert "verbatim" in why["invoice_total_arithmetic"]


def test_absent_field_failure_is_retryable():
    report = _report(_fail("mandatory_fields", ["vendor_name"]))
    conf = _conf(0.0, vendor_name=(None, 0.0, ["absent"]))
    retryable, blocking, _ = classify_failures(report, conf)
    assert retryable == ["mandatory_fields"]
    assert blocking == []


def test_duplicate_invoice_is_always_blocking():
    report = _report(_fail("duplicate_invoice", ["vendor_name", "invoice_number"]))
    conf = _conf(1.0, vendor_name=("ACME", 1.0, GROUNDED),
                 invoice_number=("INV-1", 1.0, GROUNDED))
    retryable, blocking, why = classify_failures(report, conf)
    assert blocking == ["duplicate_invoice"]
    assert "document" in why["duplicate_invoice"]


# ---------- guardrails ----------

def test_retry_is_refused_when_all_failures_are_blocking():
    """Agent asks to retry a duplicate; the graph overrules it. This is what
    stops a self-directed agent from burning compute on unfixable documents."""
    provider = FakeProvider({"decision": "retry", "reasoning": "let me try again"})
    repro = FakeReprocessor([])
    agent = ReviewAgent(provider, repro, max_attempts=3)
    out = agent.review(
        document_id="d1",
        data={},
        confidence=_conf(1.0, vendor_name=("ACME", 1.0, GROUNDED)),
        validation=_report(_fail("duplicate_invoice", ["vendor_name"])),
    )
    assert out.decision is ReviewDecision.ESCALATE
    assert out.overridden is True
    assert "blocking" in out.override_reason
    assert repro.calls == 0          # no wasted extraction


def test_retry_budget_terminates_the_loop():
    """Agent wants to retry forever; attempts ceiling forces escalation."""
    provider = FakeProvider(
        {"decision": "retry", "reasoning": "again", "retry_hint": "look harder"},
        {"decision": "retry", "reasoning": "again", "retry_hint": "look harder"},
        {"decision": "retry", "reasoning": "again", "retry_hint": "look harder"},
    )
    conf = _conf(0.0, vendor_name=(None, 0.0, ["absent"]))
    val = _report(_fail("mandatory_fields", ["vendor_name"]))
    repro = FakeReprocessor([(({}), conf, val), (({}), conf, val)])
    agent = ReviewAgent(provider, repro, max_attempts=2)

    out = agent.review(document_id="d1", data={}, confidence=conf, validation=val)

    assert out.decision is ReviewDecision.ESCALATE
    assert out.overridden is True
    assert "budget exhausted" in out.override_reason
    assert out.attempts == 2
    assert repro.calls == 1          # exactly one retry, then stop


def test_accept_is_overridden_when_blocking_failures_exist():
    provider = FakeProvider({"decision": "accept", "reasoning": "looks fine to me"})
    agent = ReviewAgent(provider, None, max_attempts=2)
    out = agent.review(
        document_id="d1",
        data={},
        confidence=_conf(1.0, invoice_date=("2027-12-25", 1.0, GROUNDED)),
        validation=_report(_fail("future_date", ["invoice_date"])),
    )
    assert out.decision is ReviewDecision.ESCALATE
    assert out.overridden is True
    assert "accepted despite blocking" in out.override_reason


def test_clean_document_is_accepted():
    provider = FakeProvider({"decision": "accept", "reasoning": "all checks pass"})
    agent = ReviewAgent(provider, None, max_attempts=2)
    out = agent.review(
        document_id="d1", data={"total": 118.0},
        confidence=_conf(1.0, total=(118.0, 1.0, GROUNDED)),
        validation=_report(),
    )
    assert out.decision is ReviewDecision.ACCEPT
    assert out.overridden is False


def test_successful_retry_reaches_accept():
    provider = FakeProvider(
        {"decision": "retry", "reasoning": "vendor missing", "retry_hint": "vendor is at top"},
        {"decision": "accept", "reasoning": "vendor recovered"},
    )
    good_conf = _conf(1.0, vendor_name=("ACME", 1.0, GROUNDED))
    repro = FakeReprocessor([({"vendor_name": "ACME"}, good_conf, _report())])
    agent = ReviewAgent(provider, repro, max_attempts=3)

    out = agent.review(
        document_id="d1", data={},
        confidence=_conf(0.0, vendor_name=(None, 0.0, ["absent"])),
        validation=_report(_fail("mandatory_fields", ["vendor_name"])),
    )
    assert out.decision is ReviewDecision.ACCEPT
    assert out.attempts == 2
    assert repro.calls == 1
    assert len(out.history) == 2      # full audit trail of both decisions


def test_unparseable_agent_output_escalates_never_accepts():
    class Garbage:
        name = "garbage"
        def complete(self, *, system, prompt, json_schema=None):
            return LLMResponse(text="I think it's probably fine?", model="g", latency_ms=1.0)

    agent = ReviewAgent(Garbage(), None, max_attempts=2)
    out = agent.review(document_id="d1", data={}, confidence=_conf(1.0), validation=_report())
    assert out.decision is ReviewDecision.ESCALATE


def test_retry_without_reprocessor_escalates_and_does_not_loop():
    """REGRESSION: production hit an infinite loop here.

    The agent asked to retry, the retry node no-opped because reprocessor was
    None, `attempts` never incremented, and the budget guard never fired —
    assess->decide->retry spun until LangGraph's recursion limit threw, ~50
    wasted model calls per document.

    Root cause: the termination counter only incremented inside the reprocessor
    branch, coupling a safety invariant to an optional collaborator.
    """
    provider = FakeProvider({"decision": "retry", "reasoning": "let me look again",
                             "retry_hint": "try harder"})
    agent = ReviewAgent(provider, reprocessor=None, max_attempts=3)

    out = agent.review(
        document_id="d1",
        data={},
        confidence=_conf(0.0, vendor_name=(None, 0.0, ["absent"])),
        validation=_report(_fail("mandatory_fields", ["vendor_name"])),
    )

    assert out.decision is ReviewDecision.ESCALATE
    assert out.overridden is True
    assert "no reprocessor" in out.override_reason
    assert provider.calls == 1          # decided once, did not spin


def test_retry_node_always_increments_attempts():
    """The termination invariant, asserted directly: no path through _retry may
    leave `attempts` unchanged, regardless of reprocessor configuration."""
    agent_no_repro = ReviewAgent(FakeProvider({"decision": "accept", "reasoning": "x"}),
                                 reprocessor=None, max_attempts=3)
    assert agent_no_repro._retry({"attempts": 1})["attempts"] == 2

    agent_with_repro = ReviewAgent(
        FakeProvider({"decision": "accept", "reasoning": "x"}),
        FakeReprocessor([({}, _conf(1.0), _report())]),
        max_attempts=3,
    )
    assert agent_with_repro._retry({"attempts": 4, "retry_hint": None})["attempts"] == 5
