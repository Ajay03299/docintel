REVIEW_SYSTEM_PROMPT = """You are a document processing review agent for an
accounts-payable pipeline. You are given an extraction, its confidence evidence,
and validation results. Decide what happens to the document.

Options:
- accept:   the extraction is trustworthy and the document is valid.
- retry:    the EXTRACTION is at fault and another attempt may fix it.
- escalate: a human must review this (the document itself is problematic, or
            retries cannot help).
- reject:   this is not a processable invoice at all (e.g. no invoice data present).

Rules you must follow:
- Only choose 'retry' if the evidence lists retryable failures. If every failure
  is blocking, retrying is wasted compute — escalate instead.
- Never choose 'accept' while blocking failures exist.
- Base your reasoning on the specific evidence given. Cite field names and rule ids.
- Be concise: two or three sentences of reasoning."""


def build_review_prompt(
    *,
    data: dict,
    confidence: dict,
    validation: dict,
    retryable: list[str],
    blocking: list[str],
    why: dict[str, str],
    attempts: int,
    max_attempts: int,
) -> str:
    lines = [
        f"ATTEMPT {attempts} of {max_attempts} allowed.",
        "",
        f"OVERALL CONFIDENCE: {confidence.get('overall')} "
        f"(strategy: {confidence.get('strategy')})",
        "",
        "FIELD CONFIDENCE:",
    ]
    for f in confidence.get("fields", []):
        lines.append(
            f"  - {f['field']}: {f['confidence']} | value={f.get('value')!r} "
            f"| {', '.join(f.get('signals', []))}"
        )

    lines += ["", f"VALIDATION: {validation.get('overall')}", ""]
    for r in validation.get("results", []):
        if r["severity"] in ("fail", "warning"):
            lines.append(f"  [{r['severity'].upper()}] {r['rule_id']}: {r['reason']}")
            if r.get("suggested_fix"):
                lines.append(f"       suggested fix: {r['suggested_fix']}")

    scored = confidence.get("fields", [])
    if scored and all(f["confidence"] == 0.0 for f in scored):
        lines += [
            "",
            "SIGNAL: NO invoice fields were found at all. This strongly suggests the "
            "document is not an invoice. Prefer 'reject' over 'retry' — re-reading a "
            "document that contains no invoice data will not produce invoice data.",
        ]

    lines += ["", "FAILURE ANALYSIS (computed deterministically, trust this):"]
    if retryable:
        for rid in retryable:
            lines.append(f"  RETRYABLE  {rid}: {why.get(rid, '')}")
    if blocking:
        for rid in blocking:
            lines.append(f"  BLOCKING   {rid}: {why.get(rid, '')}")
    if not retryable and not blocking:
        lines.append("  (no failures)")

    lines += ["", "Decide: accept, retry, escalate, or reject."]
    return "\n".join(lines)
