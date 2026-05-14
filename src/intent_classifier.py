"""
Phase 2.2 — Intent Classification & Refusal Handling

Responsibilities:
  1. Receive a ProcessedQuery (already PII-clean from Phase 2.1).
  2. Classify the query intent into one of three categories:
       FACTUAL      → proceed to Phase 2.3 retrieval
       ADVISORY     → bypass retrieval, return static refusal response
       OUT_OF_SCOPE → bypass retrieval, return out-of-scope refusal response
  3. For FACTUAL queries, also detect if the query is MIXED (factual +
     advisory in the same message) and flag it — the advisory part triggers
     refusal even if a factual part is present (per phase2_edge_cases.md).
  4. Return a ClassifiedQuery dataclass consumed by Phase 2.3.

Classification approach: keyword/pattern matching on the normalised query.
No LLM call is made here — the vocabulary of advisory/speculative language
is small and well-defined for this domain. This keeps Phase 2.2 fast,
deterministic, and free of hallucination risk.

Edge cases handled (per phase2_edge_cases.md):
  - Mixed Intent Query  : advisory keywords anywhere in the query trigger
                          refusal, even if factual keywords are also present.
  - Out-of-Scope Query  : non-HDFC fund mentions or general market questions
                          are caught and refused with a scope clarification.
  - Prompt Injection    : jailbreak patterns (ignore instructions, act as,
                          pretend you are, etc.) are detected and refused.
"""

import re
from dataclasses import dataclass, field
from enum import Enum

from query_processor import ProcessedQuery


# ---------------------------------------------------------------------------
# Intent enum
# ---------------------------------------------------------------------------

class Intent(str, Enum):
    FACTUAL      = "factual"
    ADVISORY     = "advisory"
    OUT_OF_SCOPE = "out_of_scope"
    INJECTION    = "injection"       # prompt injection attempt


# ---------------------------------------------------------------------------
# Keyword / pattern lists
# ---------------------------------------------------------------------------

# Advisory / speculative language — triggers refusal
_ADVISORY_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bshould i\b",
        r"\bshould we\b",
        r"\bis it (good|bad|safe|worth|better|best)\b",
        r"\bwould you recommend\b",
        r"\bdo you recommend\b",
        r"\badvise\b",
        r"\badvice\b",
        r"\bsuggestion\b",
        r"\bsuggested?\b",
        r"\bwhich (fund|scheme) (is|are) better\b",
        r"\bwhich (fund|scheme) should\b",
        r"\bwhich.{0,30}(fund|scheme).{0,20}(better|best|good|recommend)\b",
        r"\bcompare\b",
        r"\bcomparison\b",
        r"\bbetter (than|option|choice)\b",
        r"\bbest (fund|scheme|option|choice)\b",
        r"\bworth investing\b",
        r"\bworth (it|buying)\b",
        r"\bpredict\b",
        r"\bforecast\b",
        r"\bfuture (return|performance|growth)\b",
        r"\bexpected return\b",
        r"\breturn.{0,20}(expect|anticipate|project)\b",
        r"\b(expect|anticipate).{0,20}return\b",
        r"\bwill (it|the fund|this|\w+ fund|\w+ cap) (grow|perform|return|give)\b",
        r"\bwill \w+ \w+ fund (grow|perform|return|give)\b",
        r"\bwill .{0,30}(grow|perform|outperform|give returns?)\b",
        r"\bcan i (make|earn|get) (money|profit|return)\b",
        r"\b(is|are).{0,20}(good|bad|safe|worth|right).{0,20}(investment|invest|option)\b",
        r"\b(good|bad|safe|worth|right).{0,20}investment\b",
        r"\bguaranteed\b",
        r"\bguarantee\b",
        r"\bopinion\b",
        r"\bthink (about|of)\b",
        r"\bfeel (about|that)\b",
    ]
]

# Out-of-scope: non-HDFC AMCs, general market, stocks, crypto
_OUT_OF_SCOPE_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        # Other AMCs
        r"\b(sbi|icici|axis|kotak|nippon|mirae|dsp|franklin|tata|uti|aditya birla|sundaram|invesco)\b.*(fund|scheme|sip|nav)",
        # General market / non-MF topics
        r"\b(stock|share|equity|nse|bse|sensex|nifty 50)\b.*(buy|sell|invest|price|target)",
        r"\b(buy|sell|invest).*(stocks?|shares?|equity)\b",
        r"\bcrypto(currency)?\b",
        r"\bbitcoin\b",
        r"\breal estate\b",
        r"\bfixed deposit\b",
        r"\bppf\b",
        r"\bnps\b",
        r"\binsurance\b",
        r"\bterm plan\b",
        # Explicitly out-of-scope fund types
        r"\bdebt fund\b",
        r"\bliquid fund\b",
        r"\bhybrid fund\b",
        r"\barbitrage fund\b",
        # Commodities / precious metals (not covered HDFC MF corpus)
        r"\b(gold|silver|platinum)\b.{0,50}\b(rate|price|today|spot)\b",
        r"\b(rate|price)\b.{0,30}\b(gold|silver|platinum)\b",
        r"\bcommodit(y|ies)\b.{0,25}\b(price|rate)\b",
        r"\bcrude oil\b.{0,25}\b(price|rate)\b",
    ]
]

# Prompt injection / jailbreak attempts
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bignore (previous|above|all|prior|your) (instructions?|prompt|rules?|constraints?)\b",
        r"\bforget (everything|all|your instructions?|your rules?)\b",
        r"\bact as\b",
        r"\bpretend (you are|to be|that you)\b",
        r"\byou are now\b",
        r"\byour new (role|persona|instructions?)\b",
        r"\bdo anything now\b",
        r"\bdan mode\b",
        r"\bjailbreak\b",
        r"\bbypass (the|your|all) (rules?|filters?|restrictions?|guardrails?)\b",
        r"\bdisregard\b",
        r"\boverride\b",
        r"\bsystem prompt\b",
    ]
]

# Factual topic keywords — presence of these (without advisory language)
# confirms a factual intent. Used as a positive signal in Tier 3 fallback.
_FACTUAL_KEYWORDS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bexpense ratio\b",
        r"\bexit load\b",
        r"\bminimum sip\b",
        r"\bmin(imum)? sip\b",
        r"\bsip amount\b",
        r"\blumpsum\b",
        r"\bminimum investment\b",
        r"\bnav\b",
        r"\baum\b",
        r"\briskometer\b",
        r"\brisk (level|rating|category)\b",
        r"\bbenchmark\b",
        r"\bfund manager\b",
        r"\block.in\b",
        r"\b80c\b",
        r"\belss\b",
        r"\btax (saver|saving|deduction|benefit)\b",
        r"\bwhat is\b",
        r"\bwhat are\b",
        r"\bhow much\b",
        r"\btell me (about|the)\b",
    ]
]

# ---------------------------------------------------------------------------
# Refusal response templates
#
# URL policy (Phase 2.5):
#   ADVISORY     → no URLs in refusal text; has_citation_url=False
#   OUT_OF_SCOPE → no URLs in refusal text; has_citation_url=False
#   INJECTION    → NO URL
#   UNKNOWN      → NO URL
#   PII          → NO URL
# ---------------------------------------------------------------------------

ADVISORY_REFUSAL = (
    "I'm sorry — I can only share factual details about the HDFC Mutual Fund schemes in this assistant. "
    "I'm not able to offer investment advice, recommendations, or performance predictions. "
    "For personal guidance, please speak with a SEBI-registered investment advisor, or read investor education "
    "materials from the Association of Mutual Funds in India (AMFI)."
)

OUT_OF_SCOPE_REFUSAL = (
    "I'm sorry — that topic is outside what I can help with here. "
    "I only answer factual questions about these HDFC Mutual Fund schemes: "
    "Mid Cap, Flexi Cap, Focused, ELSS Tax Saver, and Large Cap. "
    "For anything else, please check official sources or a qualified professional."
)

INJECTION_REFUSAL = (
    "I'm sorry, but I can't process that request. "
    "I'm a facts-only assistant for HDFC Mutual Fund scheme information. "
    "Please ask a factual question about one of the supported HDFC fund schemes."
)

# Used by Phase 2.3 when retrieval confidence is below threshold,
# or when no matching chunk is found for the query.
# No URL is attached — the system cannot verify which source would answer
# the question, so linking any URL would be misleading.
UNKNOWN_ANSWER_RESPONSE = (
    "I'm sorry — I don't have verified information about that in our HDFC Mutual Fund sources. "
    "I can only help with factual questions about the five supported HDFC schemes we cover "
    "(expense ratio, NAV, exit load, minimum SIP, ELSS tax details, benchmark, riskometer, and similar). "
    "Could you rephrase your question around one of those topics?"
)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ClassifiedQuery:
    """
    Output of the intent classifier, consumed by Phase 2.3 (retrieval)
    or returned directly to the user if intent is non-factual.

    Attributes:
        processed_query  : The upstream ProcessedQuery object.
        intent           : Classified intent (FACTUAL / ADVISORY / etc.).
        should_retrieve  : True only when intent is FACTUAL — tells Phase 2.3
                           to proceed with vector store retrieval.
        refusal_response : Pre-built response string for non-factual intents.
                           Empty string when intent is FACTUAL.
        has_citation_url : Legacy flag for Phase 2.5: if True, append manifest
                           date footer after refusal text. Refusals do not embed
                           URLs; keep False for advisory and out-of-scope.
        advisory_signals : Advisory keyword matches found (for logging).
        mixed_intent     : True if both factual and advisory signals present.
    """
    processed_query:  ProcessedQuery
    intent:           Intent
    should_retrieve:  bool
    refusal_response: str = ""
    has_citation_url: bool = False   # Phase 2.5 checks this before appending a URL
    advisory_signals: list[str] = field(default_factory=list)
    mixed_intent:     bool = False


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def classify_intent(processed_query: ProcessedQuery) -> ClassifiedQuery:
    """
    Classify the intent of a PII-clean query.

    Classification priority (highest to lowest):
      1. Injection attempt  → INJECTION refusal
      2. Advisory language  → ADVISORY refusal (even if factual parts present)
      3. Out-of-scope topic → OUT_OF_SCOPE refusal
      4. Default            → FACTUAL (proceed to retrieval)

    Args:
        processed_query: Output of Phase 2.1 process_query().
                         Must have is_rejected=False before calling this.

    Returns:
        ClassifiedQuery with intent and should_retrieve set appropriately.
    """
    query = processed_query.normalised_query

    # --- 1. Prompt injection check (highest priority) ---
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(query):
            return ClassifiedQuery(
                processed_query=processed_query,
                intent=Intent.INJECTION,
                should_retrieve=False,
                refusal_response=INJECTION_REFUSAL,
                has_citation_url=False,   # security rejection — no URL
            )

    # --- 2. Advisory / speculative language check ---
    advisory_hits = [
        pattern.pattern
        for pattern in _ADVISORY_PATTERNS
        if pattern.search(query)
    ]

    if advisory_hits:
        # Check if factual keywords are also present (mixed intent)
        has_factual = any(p.search(query) for p in _FACTUAL_KEYWORDS)
        return ClassifiedQuery(
            processed_query=processed_query,
            intent=Intent.ADVISORY,
            should_retrieve=False,
            refusal_response=ADVISORY_REFUSAL,
            has_citation_url=False,
            advisory_signals=advisory_hits,
            mixed_intent=has_factual,
        )

    # --- 3. Out-of-scope check ---
    for pattern in _OUT_OF_SCOPE_PATTERNS:
        if pattern.search(query):
            return ClassifiedQuery(
                processed_query=processed_query,
                intent=Intent.OUT_OF_SCOPE,
                should_retrieve=False,
                refusal_response=OUT_OF_SCOPE_REFUSAL,
                has_citation_url=False,
            )

    # --- 4. Default: treat as factual ---
    return ClassifiedQuery(
        processed_query=processed_query,
        intent=Intent.FACTUAL,
        should_retrieve=True,
        has_citation_url=False,   # citation URL comes from chunk metadata in Phase 2.5
    )
