"""Prompt-injection defense for untrusted document text.

Runs at the trust boundary — BEFORE text enters the LLM prompt — because
validation and review run AFTER extraction, by which point an injection has
already executed. Defense must sit where the untrusted input crosses into the
model, i.e. in Engine 2.

Two functions, two jobs:
  sanitize_document_text — neutralize STRUCTURAL attacks (delimiter spoofing,
    control chars) that let attacker text impersonate the prompt's own framing.
    Does NOT strip natural language: "please remit payment" is a valid invoice
    phrase, so we cannot reject imperative sentences.
  scan_for_injection — detect injection PATTERNS as a signal (lower confidence,
    flag for review), never as a hard gate, since a legitimate document could
    quote such phrases.

Neither is sufficient alone. They compose with two defenses already in the
pipeline: Ollama's schema-constrained decoding (the model physically cannot
emit anything outside the invoice schema, so format hijacking is impossible),
and arithmetic validation (a manipulated total breaks subtotal+tax=total).
"""

import re
import unicodedata

# Attacker-supplied delimiters that mimic our own prompt framing. We wrap
# document text in "=== DOCUMENT TEXT START/END ===", so text containing those
# markers (or common instruction fences) is trying to escape the data channel.
_DELIMITER_SPOOFS = [
    re.compile(r"={2,}\s*document\s+text\s+(start|end)\s*={2,}", re.IGNORECASE),
    re.compile(r"={2,}\s*(system|user|assistant|instruction)s?\s*={2,}", re.IGNORECASE),
    re.compile(r"```+\s*(system|instruction)", re.IGNORECASE),
]

# Injection PATTERNS — presence is a signal, not a verdict.
_INJECTION_PATTERNS = [
    (re.compile(r"ignore\s+(all\s+)?(previous|above|prior|earlier)\s+(instructions?|prompts?|context)", re.IGNORECASE), "override_instruction"),
    (re.compile(r"disregard\s+(the\s+)?(above|previous|prior|system)", re.IGNORECASE), "disregard_instruction"),
    (re.compile(r"forget\s+(everything|all|your\s+instructions?)", re.IGNORECASE), "forget_instruction"),
    (re.compile(r"you\s+are\s+now\s+(a|an)\b", re.IGNORECASE), "role_reassignment"),
    (re.compile(r"new\s+(instructions?|rules?|task)\s*:", re.IGNORECASE), "new_instruction"),
    (re.compile(r"^\s*(system|assistant|user)\s*:", re.IGNORECASE | re.MULTILINE), "role_marker"),
    (re.compile(r"\bset\s+\w+\s+to\s+", re.IGNORECASE), "field_override_command"),
    (re.compile(r"(system\s+prompt|your\s+instructions?|the\s+prompt)", re.IGNORECASE), "prompt_reference"),
]


def sanitize_document_text(text: str) -> tuple[str, list[str]]:
    """Neutralize structural attacks. Returns (clean_text, notes)."""
    notes: list[str] = []

    # 1. Normalize unicode so homoglyph/zero-width tricks can't smuggle markers.
    normalized = unicodedata.normalize("NFKC", text)
    normalized = "".join(
        c for c in normalized if unicodedata.category(c)[0] != "C" or c in "\n\t"
    )
    if normalized != text:
        notes.append("normalized_unicode_and_stripped_control_chars")

    # 2. Neutralize delimiter spoofs by defanging the markers (don't delete the
    #    surrounding text — it may carry real data — just break the mimicry).
    result = normalized
    for pattern in _DELIMITER_SPOOFS:
        if pattern.search(result):
            result = pattern.sub("[removed-delimiter]", result)
            notes.append("neutralized_delimiter_spoof")

    return result, notes


def scan_for_injection(text: str) -> list[str]:
    """Detect injection patterns. Returns a list of matched pattern labels
    (empty if clean). This is EVIDENCE for the confidence/validation layers,
    not a gate — a legitimate document could quote such phrases."""
    found: list[str] = []
    for pattern, label in _INJECTION_PATTERNS:
        if pattern.search(text):
            found.append(label)
    return found
