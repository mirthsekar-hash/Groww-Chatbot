"""
Phase 3.3 — Backend RAG orchestration (Phases 2.1 through 2.5)

Wires query processing, intent classification, metadata-filtered retrieval,
Groq generation, and response formatting into a single `answer_query` call
for the HTTP API and any other clients.
"""

from __future__ import annotations

import logging
import threading

from intent_classifier import classify_intent
from perf import perf_span
from query_processor import process_query
from response_format import format_phase25_response, generate_and_format_response
from retriever import RetrievalResult, load_retrieval_components, retrieve

logger = logging.getLogger(__name__)

# FastAPI runs sync routes in a thread pool; startup preloads the embedding model
# on the main/event-loop path. SentenceTransformer / torch are not safe for
# concurrent cross-thread use — serialize all loads and inference.
PIPELINE_LOCK = threading.Lock()


class ChatPipeline:
    """
    Loads embedding model + Chroma once; reused across requests in one process.
    All retrieval / encode paths must run under PIPELINE_LOCK (see answer_query).
    """

    def __init__(self) -> None:
        self._model = None
        self._chroma_client = None

    def _load_if_needed_nolock(self) -> None:
        """Load embedding model + Chroma; caller must hold PIPELINE_LOCK."""
        if self._model is not None:
            return
        logger.info("Loading embedding model and ChromaDB client…")
        self._model, self._chroma_client = load_retrieval_components()
        logger.info("Retrieval stack ready.")

    def ensure_loaded(self) -> None:
        """Eager-load retrieval stack (sentence-transformers + Chroma)."""
        with PIPELINE_LOCK:
            self._load_if_needed_nolock()

    def answer_query(self, raw_message: str) -> str:
        """
        Run the full pipeline and return the final user-facing string.

        Phases: 2.1 → 2.2 → (2.3 + 2.4 + 2.5) for factual queries;
        refusals and PII use the same formatting rules as `response_format`.
        """
        with perf_span("query+intent"):
            processed = process_query(raw_message)
            if processed.is_rejected:
                return processed.rejection_reason

            classified = classify_intent(processed)
            empty_retrieval = RetrievalResult(chunks=[], is_unknown=True)

            if not classified.should_retrieve:
                return format_phase25_response(classified, empty_retrieval, "")

        retrieval: RetrievalResult
        with PIPELINE_LOCK:
            with perf_span("embed+retrieve"):
                self._load_if_needed_nolock()
                assert self._model is not None and self._chroma_client is not None
                retrieval = retrieve(classified, self._model, self._chroma_client)

        with perf_span("groq+format"):
            return generate_and_format_response(classified, retrieval)


_pipeline: ChatPipeline | None = None


def get_pipeline() -> ChatPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = ChatPipeline()
    return _pipeline
