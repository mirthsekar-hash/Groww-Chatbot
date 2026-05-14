"""
Phase 2.3 — Semantic Retrieval (Metadata-Filtered)

Strategy: Metadata-Filtered Semantic Retrieval
  Combines bge-small-en vector similarity with ChromaDB `where` clause
  filtering on scheme_name and chunk_type.

  Pure semantic search is insufficient for this corpus because 4 of 5 funds
  share near-identical exit_load and min_investment chunk text — only the
  fund name differs. A metadata filter pins the result to the correct fund.

Retrieval pipeline:
  Stage 1 — Entity Extraction
    Parse the normalised query using keyword alias maps to extract:
      fund_name : one of the 5 HDFC scheme names (or None)
      topic     : one of the 6 chunk_types (or None)

  Stage 2 — ChromaDB Query (3-tier fallback)
    Tier 1 — Both fund_name + topic extracted
              where = {scheme_name: X, chunk_type: Y}, n_results=1
    Tier 2 — Only fund_name extracted
              where = {scheme_name: X}, n_results=3, semantic ranking
    Tier 3 — Neither extracted (generic query)
              pure semantic search, n_results=3

  Confidence check
    If the top result's cosine similarity < CONFIDENCE_THRESHOLD (0.55),
    the retrieval is treated as a miss and UNKNOWN_ANSWER_RESPONSE is
    returned — no URL attached (per URL policy in Phase 2.2).

  Ambiguous fund query (edge case from phase2_edge_cases.md)
    If topic is extracted but fund_name is None, all 5 funds are queried
    for that topic and results are returned together so the LLM can list
    all values (e.g., "expense ratios for all HDFC funds").

BGE query prefix:
  All query embeddings use the prefix:
    "Represent this sentence for searching relevant passages: <query>"
  Document embeddings in the store were indexed WITHOUT this prefix.
"""

import sys
import os
from dataclasses import dataclass, field
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

# Phase 2.2 imports
sys.path.insert(0, os.path.dirname(__file__))
from intent_classifier import ClassifiedQuery, UNKNOWN_ANSWER_RESPONSE

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
VECTORSTORE_DIR = BASE_DIR / "data" / "vectorstore"

COLLECTION_NAME   = "hdfc_mutual_funds"
EMBEDDING_MODEL   = "BAAI/bge-small-en"
BGE_QUERY_PREFIX  = "Represent this sentence for searching relevant passages: "

# Cosine similarity below this threshold → treat as retrieval miss
# (cosine distance from ChromaDB is 1 - similarity, so threshold = 1 - 0.55)
CONFIDENCE_THRESHOLD      = 0.55
CONFIDENCE_DIST_THRESHOLD = 1 - CONFIDENCE_THRESHOLD   # 0.45

# ---------------------------------------------------------------------------
# Alias maps  (fixed vocabulary — no NLP model required)
# ---------------------------------------------------------------------------

# Maps query keywords → canonical scheme_name stored in ChromaDB metadata
FUND_ALIASES: dict[str, str] = {
    "mid cap":   "HDFC Mid Cap Fund Direct Growth",
    "midcap":    "HDFC Mid Cap Fund Direct Growth",
    "flexi cap": "HDFC Flexi Cap Direct Plan Growth",
    "flexicap":  "HDFC Flexi Cap Direct Plan Growth",
    "flexi":     "HDFC Flexi Cap Direct Plan Growth",
    "focused":   "HDFC Focused Fund Direct Growth",
    "focus":     "HDFC Focused Fund Direct Growth",
    "elss":      "HDFC ELSS Tax Saver Fund Direct Plan Growth",
    "tax saver": "HDFC ELSS Tax Saver Fund Direct Plan Growth",
    "tax-saver": "HDFC ELSS Tax Saver Fund Direct Plan Growth",
    "large cap": "HDFC Large Cap Fund Direct Growth",
    "largecap":  "HDFC Large Cap Fund Direct Growth",
}

# Maps query keywords → chunk_type stored in ChromaDB metadata
TOPIC_ALIASES: dict[str, str] = {
    "expense ratio":    "expense_ratio",
    "expense":          "expense_ratio",
    "ter":              "expense_ratio",
    "exit load":        "exit_load",
    "exit":             "exit_load",
    "redemption":       "exit_load",
    "lock-in":          "exit_load",
    "lock in":          "exit_load",
    "lockin":           "exit_load",
    "sip":              "min_investment",
    "minimum sip":      "min_investment",
    "min sip":          "min_investment",
    "minimum":          "min_investment",
    "lumpsum":          "min_investment",
    "lump sum":         "min_investment",
    "minimum investment": "min_investment",
    "benchmark":        "benchmark",
    "index":            "benchmark",
    "riskometer":       "overview",
    "risk":             "overview",
    "risk level":       "overview",
    "risk rating":      "overview",
    "aum":              "overview",
    "fund size":        "overview",
    "nav":              "overview",
    "fund manager":     "overview",
    "manager":          "overview",
    "category":         "overview",
    "about":            "overview",
    "80c":              "elss_tax_benefit",
    "section 80c":      "elss_tax_benefit",
    "tax":              "elss_tax_benefit",
    "tax benefit":      "elss_tax_benefit",
    "tax deduction":    "elss_tax_benefit",
    "tax saving":       "elss_tax_benefit",
}

# All canonical scheme names — used for ambiguous fund queries
ALL_SCHEMES: list[str] = [
    "HDFC Mid Cap Fund Direct Growth",
    "HDFC Flexi Cap Direct Plan Growth",
    "HDFC Focused Fund Direct Growth",
    "HDFC ELSS Tax Saver Fund Direct Plan Growth",
    "HDFC Large Cap Fund Direct Growth",
]

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class RetrievalResult:
    """
    Output of Phase 2.3, consumed by Phase 2.4 (prompt assembly).

    Attributes:
        chunks          : List of retrieved chunk dicts (text + metadata).
                          Empty if retrieval failed or confidence too low.
        is_unknown      : True when no confident match was found.
                          Phase 2.4 must return UNKNOWN_ANSWER_RESPONSE
                          without attaching any URL.
        unknown_response: Pre-built response text when is_unknown=True.
        tier_used       : Which retrieval tier was applied (1, 2, or 3).
        fund_name       : Extracted fund name (or None).
        topic           : Extracted topic / chunk_type (or None).
        is_ambiguous    : True when topic found but fund_name is None —
                          results cover all 5 funds for that topic.
        top_score       : Cosine similarity of the best result (0–1).
    """
    chunks:           list[dict]
    is_unknown:       bool = False
    unknown_response: str  = ""
    tier_used:        int  = 0
    fund_name:        str | None = None
    topic:            str | None = None
    is_ambiguous:     bool = False
    top_score:        float = 0.0


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------

def _extract_entities(query: str) -> tuple[str | None, str | None]:
    """
    Extract fund_name and topic from the normalised query using alias maps.

    Matching is case-insensitive and uses longest-match-first ordering
    (multi-word aliases like "mid cap" are checked before single words).

    Returns:
        (fund_name, topic) — either or both may be None.
    """
    q = query.lower()

    # Sort aliases by length descending so "mid cap" matches before "cap"
    fund_name = None
    for alias in sorted(FUND_ALIASES, key=len, reverse=True):
        if alias in q:
            fund_name = FUND_ALIASES[alias]
            break

    topic = None
    for alias in sorted(TOPIC_ALIASES, key=len, reverse=True):
        if alias in q:
            topic = TOPIC_ALIASES[alias]
            break

    return fund_name, topic


# ---------------------------------------------------------------------------
# ChromaDB helpers
# ---------------------------------------------------------------------------

def _get_collection(client: chromadb.PersistentClient) -> chromadb.Collection:
    return client.get_collection(name=COLLECTION_NAME)


def _embed_query(query: str, model: SentenceTransformer) -> list[float]:
    """Embed a user query with the BGE query prefix."""
    prefixed = BGE_QUERY_PREFIX + query
    return model.encode(prefixed, normalize_embeddings=True).tolist()


def _chroma_to_chunks(results: dict) -> list[dict]:
    """
    Convert ChromaDB query results into a flat list of chunk dicts,
    each containing 'text', 'metadata', and 'score' (cosine similarity).
    """
    chunks = []
    docs      = results.get("documents", [[]])[0]
    metas     = results.get("metadatas",  [[]])[0]
    distances = results.get("distances",  [[]])[0]

    for doc, meta, dist in zip(docs, metas, distances):
        chunks.append({
            "text":     doc,
            "metadata": meta,
            "score":    round(1 - dist, 4),   # cosine distance → similarity
        })
    return chunks


# ---------------------------------------------------------------------------
# Core retrieval function
# ---------------------------------------------------------------------------

def retrieve(
    classified_query: ClassifiedQuery,
    model: SentenceTransformer,
    client: chromadb.PersistentClient,
) -> RetrievalResult:
    """
    Execute metadata-filtered semantic retrieval for a FACTUAL query.

    Args:
        classified_query : Output of Phase 2.2 with intent=FACTUAL.
        model            : Loaded SentenceTransformer (bge-small-en).
        client           : Connected ChromaDB PersistentClient.

    Returns:
        RetrievalResult with retrieved chunks or is_unknown=True.
    """
    query     = classified_query.processed_query.normalised_query
    collection = _get_collection(client)
    query_vec  = _embed_query(query, model)

    fund_name, topic = _extract_entities(query)

    # -----------------------------------------------------------------------
    # Ambiguous fund query (edge case: topic known, fund unknown)
    # e.g., "What is the expense ratio?" — no fund specified
    # Retrieve the topic chunk for ALL 5 funds so the LLM can list them.
    # -----------------------------------------------------------------------
    if topic and not fund_name:
        all_chunks = []
        for scheme in ALL_SCHEMES:
            results = collection.query(
                query_embeddings=[query_vec],
                n_results=1,
                where={"$and": [
                    {"scheme_name": {"$eq": scheme}},
                    {"chunk_type":  {"$eq": topic}},
                ]},
                include=["documents", "metadatas", "distances"],
            )
            chunks = _chroma_to_chunks(results)
            if chunks:
                all_chunks.extend(chunks)

        if not all_chunks:
            return RetrievalResult(
                chunks=[], is_unknown=True,
                unknown_response=UNKNOWN_ANSWER_RESPONSE,
                tier_used=1, fund_name=None, topic=topic,
            )

        top_score = max(c["score"] for c in all_chunks)
        return RetrievalResult(
            chunks=all_chunks, tier_used=1,
            fund_name=None, topic=topic,
            is_ambiguous=True, top_score=top_score,
        )

    # -----------------------------------------------------------------------
    # Tier 1 — Both fund_name and topic extracted (highest precision)
    # -----------------------------------------------------------------------
    if fund_name and topic:
        results = collection.query(
            query_embeddings=[query_vec],
            n_results=1,
            where={"$and": [
                {"scheme_name": {"$eq": fund_name}},
                {"chunk_type":  {"$eq": topic}},
            ]},
            include=["documents", "metadatas", "distances"],
        )
        chunks = _chroma_to_chunks(results)

        if not chunks or chunks[0]["score"] < CONFIDENCE_THRESHOLD:
            return RetrievalResult(
                chunks=[], is_unknown=True,
                unknown_response=UNKNOWN_ANSWER_RESPONSE,
                tier_used=1, fund_name=fund_name, topic=topic,
                top_score=chunks[0]["score"] if chunks else 0.0,
            )

        return RetrievalResult(
            chunks=chunks, tier_used=1,
            fund_name=fund_name, topic=topic,
            top_score=chunks[0]["score"],
        )

    # -----------------------------------------------------------------------
    # Tier 2 — Only fund_name extracted
    # Semantic similarity ranks the best topic chunk for that fund.
    # -----------------------------------------------------------------------
    if fund_name and not topic:
        results = collection.query(
            query_embeddings=[query_vec],
            n_results=3,
            where={"scheme_name": {"$eq": fund_name}},
            include=["documents", "metadatas", "distances"],
        )
        chunks = _chroma_to_chunks(results)

        if not chunks or chunks[0]["score"] < CONFIDENCE_THRESHOLD:
            return RetrievalResult(
                chunks=[], is_unknown=True,
                unknown_response=UNKNOWN_ANSWER_RESPONSE,
                tier_used=2, fund_name=fund_name, topic=None,
                top_score=chunks[0]["score"] if chunks else 0.0,
            )

        return RetrievalResult(
            chunks=chunks[:1], tier_used=2,   # return only top-ranked chunk
            fund_name=fund_name, topic=None,
            top_score=chunks[0]["score"],
        )

    # -----------------------------------------------------------------------
    # Tier 3 — Neither extracted (generic query)
    # Pure semantic search across the full collection.
    # -----------------------------------------------------------------------
    results = collection.query(
        query_embeddings=[query_vec],
        n_results=3,
        include=["documents", "metadatas", "distances"],
    )
    chunks = _chroma_to_chunks(results)

    if not chunks or chunks[0]["score"] < CONFIDENCE_THRESHOLD:
        return RetrievalResult(
            chunks=[], is_unknown=True,
            unknown_response=UNKNOWN_ANSWER_RESPONSE,
            tier_used=3, fund_name=None, topic=None,
            top_score=chunks[0]["score"] if chunks else 0.0,
        )

    return RetrievalResult(
        chunks=chunks[:1], tier_used=3,
        fund_name=None, topic=None,
        top_score=chunks[0]["score"],
    )


# ---------------------------------------------------------------------------
# Convenience: load model + client once (reused across requests)
# ---------------------------------------------------------------------------

def load_retrieval_components() -> tuple[SentenceTransformer, chromadb.PersistentClient]:
    """
    Load the embedding model and ChromaDB client.
    Call once at application startup and pass to retrieve() on each request.
    """
    model  = SentenceTransformer(EMBEDDING_MODEL)
    client = chromadb.PersistentClient(path=str(VECTORSTORE_DIR))
    return model, client
