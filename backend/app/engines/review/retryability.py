"""Decide whether re-running extraction could plausibly fix a failure.

Two levels:
  1. Rule capability  — can extraction EVER fix this class of failure?
  2. Grounding evidence — would it fix THIS instance?

Level 2 is the important one. If every field a rule implicates was found
verbatim in the source text, the extraction was faithful and the DOCUMENT is
wrong. Re-reading it will produce the same values, so a retry is guaranteed
waste — escalate to a human instead.
"""

from app.engines.validation.registry import get_rules
from app.schemas.validation import Severity, ValidationReport


def _grounded_fields(confidence: dict) -> set[str]:
    out: set[str] = set()
    for f in confidence.get("fields", []):
        if any("grounded_in_source" in s for s in f.get("signals", [])):
            out.add(f["field"])
    return out


def _scored_fields(confidence: dict) -> set[str]:
    return {f["field"] for f in confidence.get("fields", [])}


def classify_failures(
    validation: ValidationReport, confidence: dict
) -> tuple[list[str], list[str], dict[str, str]]:
    """Split FAIL/WARNING results into (retryable, blocking, why).

    'blocking' means: no amount of re-extraction will clear this.
    """
    rules = get_rules()
    grounded = _grounded_fields(confidence)
    scored = _scored_fields(confidence)

    retryable: list[str] = []
    blocking: list[str] = []
    why: dict[str, str] = {}

    for result in validation.results:
        if result.severity not in (Severity.FAIL, Severity.WARNING):
            continue

        rule = rules.get(result.rule_id)
        if rule is None or not rule.retryable:
            blocking.append(result.rule_id)
            why[result.rule_id] = "failure is a property of the document, not the extraction"
            continue

        implicated = [f for f in result.fields if f in scored]
        if implicated and all(f in grounded for f in implicated):
            blocking.append(result.rule_id)
            why[result.rule_id] = (
                f"all implicated fields ({', '.join(implicated)}) were found verbatim "
                "in the source text — re-extraction would read the same values"
            )
            continue

        retryable.append(result.rule_id)
        ungrounded = [f for f in implicated if f not in grounded] or result.fields
        why[result.rule_id] = (
            f"field(s) {', '.join(ungrounded) or 'n/a'} are absent or not grounded "
            "in the source — a further extraction attempt may recover them"
        )

    return retryable, blocking, why
