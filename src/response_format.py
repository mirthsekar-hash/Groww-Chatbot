"""
Phase 2.5 — Response Formatting

Post-processes LLM output (Phase 2.4) to append:
  - Exactly one citation URL from chunk metadata (`source_url`), and
  - Footer: Last updated from sources: <date>

The date is read from `data/vectorstore/manifest.json` → `ingestion_timestamp`
(authoritative KB refresh time per phase_wise_architecture.md §5.5).

Refusal paths (advisory / out-of-scope / injection) return plain text only:
no `https://` links and no manifest footer, unless `has_citation_url` is True
(legacy; currently unused for refusals). Factual answers still get one Groww
citation plus footer when grounded.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intent_classifier import ClassifiedQuery, Intent, UNKNOWN_ANSWER_RESPONSE
from retriever import RetrievalResult

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = BASE_DIR / "data" / "vectorstore" / "manifest.json"

_URL_IN_TEXT = re.compile(r"https?://\S+")

# LLM said the provided chunks do not answer the question — do not attach a
# misleading Groww citation (same policy as retrieval miss / UNKNOWN).
_LLM_DECLINES_CONTEXT_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bthe context does not contain\b",
        r"\bcontext does not contain\b",
        r"\bdoes not contain information about\b",
        r"\bnot (?:found|mentioned|available|included) in the (?:provided )?context\b",
        r"\bno information (?:is )?(?:available|found) in the (?:provided )?context\b",
        r"\bcannot (?:answer|determine).{0,100}from the (?:provided )?context\b",
        r"\bis not (?:in|within) the (?:provided )?context\b",
        r"\bbased (?:only )?on the context.*\b(?:cannot|unable to)\b",
    ]
]


def _read_manifest_date(manifest_path: Path) -> str:
    """Return YYYY-MM-DD from manifest ingestion_timestamp; fallback to UTC today."""
    try:
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)
        ts = (data.get("ingestion_timestamp") or "").strip()
        if ts:
            clean = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.date().isoformat()
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as e:
        logger.warning("Could not read manifest date from %s: %s", manifest_path, e)
    return datetime.now(timezone.utc).date().isoformat()


def strip_urls_from_text(text: str) -> str:
    """Remove http(s) URLs so the only link is the controlled citation line."""
    t = _URL_IN_TEXT.sub("", text)
    return " ".join(t.split()).strip()


def _extract_url_from_chunk(chunk: dict | None) -> str:
    if not chunk:
        return ""
    meta = chunk.get("metadata") or {}
    url = (meta.get("source_url") or "").strip()
    if url:
        return url
    citation = meta.get("citation_text") or ""
    m = _URL_IN_TEXT.search(citation)
    return m.group(0).rstrip(").,;'\"") if m else ""


def pick_primary_chunk(chunks: list[dict]) -> dict | None:
    """Choose citation source: highest retrieval score, else first chunk."""
    if not chunks:
        return None
    return max(chunks, key=lambda c: float(c.get("score", 0.0)))


def _llm_declines_context_answer(body: str) -> bool:
    """True when the model indicates the retrieved context does not support an answer."""
    t = (body or "").strip()
    if not t:
        return True
    return any(p.search(t) for p in _LLM_DECLINES_CONTEXT_PATTERNS)


def _is_unknown_body(text: str) -> bool:
    return text.strip() == UNKNOWN_ANSWER_RESPONSE.strip()


def format_phase25_response(
    classified: ClassifiedQuery,
    retrieval: RetrievalResult,
    llm_body: str,
    *,
    manifest_path: Path | None = None,
) -> str:
    """
    Apply Phase 2.5 formatting: optional URL stripping on body, one citation
    URL from retrieval metadata, and manifest-based footer date.

    Args:
        classified: Phase 2.2 output (includes processed_query for PII guard).
        retrieval: Phase 2.3 output.
        llm_body: Phase 2.4 plain text (or refusal/unknown text on factual miss).

    Returns:
        Final user-facing string.
    """
    pq = classified.processed_query
    if pq.is_rejected:
        return pq.rejection_reason

    path = manifest_path or DEFAULT_MANIFEST
    manifest_date = _read_manifest_date(path)

    if classified.intent != Intent.FACTUAL:
        text = strip_urls_from_text(classified.refusal_response)
        if classified.intent == Intent.INJECTION:
            return text
        if classified.has_citation_url:
            return f"{text}\n\nLast updated from sources: {manifest_date}"
        return text

    if retrieval.is_unknown or _is_unknown_body(llm_body) or _llm_declines_context_answer(llm_body):
        return UNKNOWN_ANSWER_RESPONSE.strip()

    primary = pick_primary_chunk(retrieval.chunks)
    url = _extract_url_from_chunk(primary)
    body = strip_urls_from_text(llm_body)

    footer = f"Last updated from sources: {manifest_date}"
    if not url:
        logger.warning("Missing source_url for citation; footer only.")
        return f"{body}\n\n{footer}"

    return f"{body}\n\n{url}\n{footer}"


def generate_and_format_response(
    classified: ClassifiedQuery,
    retrieval: RetrievalResult,
    **groq_kwargs: Any,
) -> str:
    """
    Run Phase 2.4 (Groq) then Phase 2.5 formatting. Convenience for API layers.

    groq_kwargs are forwarded to `llm_generate.generate_factual_answer`
    (e.g. groq_client=... for tests).
    """
    from llm_generate import generate_factual_answer

    q = classified.processed_query.normalised_query
    body = generate_factual_answer(q, retrieval, **groq_kwargs)
    return format_phase25_response(classified, retrieval, body)
