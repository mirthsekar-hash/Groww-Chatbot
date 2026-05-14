"""
Phase 2.4 — Prompt Assembly & LLM Generation (Groq)

Constructs a strict prompt with user query + retrieved context, then calls the
Groq Chat Completions API (OpenAI-compatible) to produce an answer.

Constraints (from phase_wise_architecture.md):
  - Answer must use ONLY the provided context.
  - Maximum 3 sentences (prompt + post-hoc enforcement).
  - Strictly factual tone; no extrapolation or investment advice.

Does NOT append the Phase 2.5 footer (date + citation link). Import
`response_format.format_phase25_response` after generation to complete Phase 2.5,
or use `response_format.generate_and_format_response` for both steps.

Environment:
  GROQ_API_KEY   — required for live generation (https://console.groq.com/)
  GROQ_MODEL     — optional; defaults to llama-3.3-70b-versatile
"""

from __future__ import annotations

import logging
import os
import re

from groq import Groq

from intent_classifier import UNKNOWN_ANSWER_RESPONSE
from retriever import RetrievalResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
MAX_SENTENCES = 3
MAX_COMPLETION_TOKENS = 220
GEN_TEMPERATURE = 0.15

SYSTEM_INSTRUCTIONS = """You are a facts-only assistant for HDFC Mutual Fund schemes covered in the project corpus.

Hard rules:
1. Answer using ONLY the information in the CONTEXT blocks. If the context does not contain enough information, say so briefly — do not guess or use outside knowledge.
2. Write at most {max_sentences} complete sentences.
3. No investment advice, recommendations, opinions, or predictions.
4. Do not compare funds or say which is "better".
5. Use a neutral, factual tone. Quote numbers and facts exactly as they appear in the context when applicable.
6. Do not include URLs, footers, or "last updated" lines in your answer — those are added by the system later.
""".format(max_sentences=MAX_SENTENCES)


def _get_model_name() -> str:
    return os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)


def format_retrieval_context(chunks: list[dict]) -> str:
    """
    Turn retrieved chunk dicts (text + metadata) into a single context string.
    Multiple chunks (e.g. ambiguous fund query) are numbered and labelled.
    """
    parts: list[str] = []
    for i, c in enumerate(chunks, 1):
        meta = c.get("metadata") or {}
        scheme = meta.get("scheme_name") or ""
        ctype = meta.get("chunk_type") or ""
        body = (c.get("text") or "").strip()
        if scheme or ctype:
            header = f"[{i}] Scheme: {scheme} | Topic: {ctype}"
        else:
            header = f"[{i}]"
        parts.append(f"{header}\n{body}")
    return "\n\n".join(parts)


def build_chat_messages(user_query: str, context_text: str) -> list[dict[str, str]]:
    """OpenAI-style messages for Groq chat.completions."""
    user_content = (
        "CONTEXT (authoritative; answer only from this material):\n\n"
        f"{context_text}\n\n"
        "---\n\n"
        f"USER QUESTION:\n{user_query.strip()}"
    )
    return [
        {"role": "system", "content": SYSTEM_INSTRUCTIONS},
        {"role": "user", "content": user_content},
    ]


def enforce_max_sentences(text: str, max_sentences: int = MAX_SENTENCES) -> str:
    """
    Trim to at most `max_sentences` sentence-like segments.
    Heuristic split on punctuation + whitespace (good enough for short answers).
    """
    t = text.strip()
    if not t:
        return t
    # Split after . ! ? keeping delimiter notion via lookahead
    pieces = re.split(r"(?<=[.!?])\s+", t)
    sentences = [s.strip() for s in pieces if s.strip()]
    if len(sentences) <= max_sentences:
        return t
    return " ".join(sentences[:max_sentences]).strip()


def generate_factual_answer(
    user_query: str,
    retrieval: RetrievalResult,
    *,
    groq_client: Groq | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> str:
    """
    Phase 2.4 entry point: assemble prompt and call Groq for a factual answer.

    Args:
        user_query: Normalised user question (same string used for retrieval).
        retrieval: Phase 2.3 output; if is_unknown or empty chunks, returns the
                   canned unknown response without calling the LLM.
        groq_client: Optional injected Groq client (for tests).
        model: Overrides GROQ_MODEL / default.
        api_key: Overrides GROQ_API_KEY when constructing a client.

    Returns:
        Plain answer text (no Phase 2.5 footer). At most MAX_SENTENCES sentences.
    """
    if retrieval.is_unknown or not retrieval.chunks:
        return retrieval.unknown_response or UNKNOWN_ANSWER_RESPONSE

    context_text = format_retrieval_context(retrieval.chunks)
    messages = build_chat_messages(user_query, context_text)
    model_name = model or _get_model_name()

    client = groq_client
    if client is None:
        key = api_key or os.environ.get("GROQ_API_KEY")
        if not key:
            logger.warning("GROQ_API_KEY is not set; cannot call Groq.")
            return UNKNOWN_ANSWER_RESPONSE
        client = Groq(api_key=key)

    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=GEN_TEMPERATURE,
            max_tokens=MAX_COMPLETION_TOKENS,
        )
    except Exception as e:
        logger.exception("Groq API call failed: %s", e)
        return UNKNOWN_ANSWER_RESPONSE

    choice = completion.choices[0]
    raw = (choice.message.content or "").strip()
    if not raw:
        logger.warning("Groq returned empty content.")
        return UNKNOWN_ANSWER_RESPONSE

    return enforce_max_sentences(raw, MAX_SENTENCES)
