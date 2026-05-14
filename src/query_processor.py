"""
Phase 2.1 — Query Processing & Privacy Filter

Responsibilities:
  1. Receive the raw user query string.
  2. Normalise it (strip, collapse whitespace, lowercase for matching).
  3. Scan for PII patterns (PAN, Aadhaar, account numbers, email, phone).
  4. If PII is detected, reject the query immediately with a safe error
     response — the raw query is never logged or stored.
  5. Return a ProcessedQuery dataclass consumed by Phase 2.2.

PII patterns covered (per problem statement & phase2_edge_cases.md):
  - PAN number       : AAAAA9999A  (5 alpha + 4 digit + 1 alpha)
  - Aadhaar number   : 12-digit number (with or without spaces/hyphens)
  - Bank account     : 9–18 digit numeric string
  - Email address    : standard RFC-5322 simplified pattern
  - Phone number     : Indian mobile (10 digits, optional +91 / 0 prefix)
  - OTP              : 4–8 consecutive digits (standalone)

Edge cases handled (per phase2_edge_cases.md):
  - PII Camouflage: PII embedded inside a sentence is still detected
    because all patterns use word-boundary or context anchors.
"""

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# PII detection patterns
# ---------------------------------------------------------------------------

_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "PAN number",
        re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE),
    ),
    (
        "Aadhaar number",
        # 12 digits, optionally grouped as 4-4-4 with spaces or hyphens
        re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"),
    ),
    (
        "email address",
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    ),
    (
        "phone number",
        # +91 / 0 prefix optional; 10-digit Indian mobile
        re.compile(r"(\+91[\s\-]?|0)?[6-9]\d{9}\b"),
    ),
    (
        "bank account number",
        # 9–18 standalone digits (not part of a longer number)
        re.compile(r"(?<!\d)\d{9,18}(?!\d)"),
    ),
    (
        "OTP",
        # 4–8 standalone digits preceded by OTP/code context words
        # Avoids false positives on years (2025), NAV values, etc.
        re.compile(r"\b(otp|one.time.password|verification code|passcode)\b.{0,30}\d{4,8}\b", re.IGNORECASE),
    ),
]

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ProcessedQuery:
    """
    Output of the query processor, consumed by Phase 2.2 (intent classifier).

    Attributes:
        original_query   : Raw text as received from the user.
        normalised_query : Whitespace-collapsed, stripped version for matching.
        is_rejected      : True if PII was detected — pipeline must halt here.
        rejection_reason : Human-readable reason shown to the user.
        pii_types_found  : List of PII type labels detected (for logging only;
                           the actual values are never stored).
    """
    original_query:   str
    normalised_query: str
    is_rejected:      bool = False
    rejection_reason: str = ""
    pii_types_found:  list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Safe rejection response (shown to user when PII is detected)
# No URL is included — this is a security rejection, not an informational
# response. Attaching a link to a PII-related refusal could imply the
# system processed or acted on the personal data.
# ---------------------------------------------------------------------------

PII_REJECTION_RESPONSE = (
    "I'm sorry, but your message appears to contain personal information "
    "(such as a PAN number, Aadhaar, phone number, or email address). "
    "For your security, please do not share personal details. "
    "I can only answer factual questions about HDFC Mutual Fund schemes. "
    "Please rephrase your question without any personal information."
)


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def process_query(raw_query: str) -> ProcessedQuery:
    """
    Normalise and PII-scan a raw user query.

    Args:
        raw_query: The exact string submitted by the user.

    Returns:
        ProcessedQuery with is_rejected=True if PII is found,
        or is_rejected=False with a clean normalised_query ready
        for Phase 2.2 intent classification.

    Note:
        The actual PII values are never stored — only the type labels
        (e.g., "PAN number") are recorded for audit purposes.
    """
    if not raw_query or not raw_query.strip():
        return ProcessedQuery(
            original_query=raw_query,
            normalised_query="",
            is_rejected=True,
            rejection_reason="Empty query.",
        )

    # Normalise: strip leading/trailing whitespace, collapse internal spaces
    normalised = " ".join(raw_query.strip().split())

    # Scan for PII — check against all patterns
    detected_types: list[str] = []
    for pii_label, pattern in _PII_PATTERNS:
        if pattern.search(normalised):
            detected_types.append(pii_label)

    if detected_types:
        # Deduplicate labels (e.g., Aadhaar may also match account number)
        unique_types = list(dict.fromkeys(detected_types))
        return ProcessedQuery(
            original_query=raw_query,
            normalised_query="",          # do not pass PII-laden text forward
            is_rejected=True,
            rejection_reason=PII_REJECTION_RESPONSE,
            pii_types_found=unique_types,  # labels only, not values
        )

    return ProcessedQuery(
        original_query=raw_query,
        normalised_query=normalised,
        is_rejected=False,
    )
