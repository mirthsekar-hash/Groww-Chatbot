"""
Phase 1.4 (Vector Storage) — ChromaDB Ingestion
Reads data/processed/embedded_chunks.json and ingests all 26 chunks
into a persistent ChromaDB collection.

Why ChromaDB?
  - Runs fully locally (no server, no API key)
  - Persists to disk at data/vectorstore/
  - Accepts pre-computed embeddings directly — we pass our bge-small-en
    vectors in, so ChromaDB does NOT re-embed anything
  - Supports metadata filtering (by scheme_name, chunk_type, is_elss, etc.)
    which Phase 2.3 uses to narrow retrieval scope

Collection design:
  - One collection: "hdfc_mutual_funds"
  - Each document = one chunk
  - IDs        : chunk_id (SHA-256 prefix, guaranteed unique)
  - Embeddings : 384-dim unit-normalised bge-small-en vectors
  - Documents  : chunk text (stored for retrieval + LLM context)
  - Metadata   : all Phase 1.3 fields, ChromaDB-safe typed
                 (booleans → "true"/"false" strings,
                  newlines in citation_text → \\n escaped)

ChromaDB metadata type rules (strictly enforced):
  Allowed  : str, int, float, bool
  NOT allowed: None, list, dict, nested objects
  → Any None value is replaced with "" (empty string)
  → is_elss bool is kept as bool (ChromaDB supports bool natively)
  → citation_text newlines are preserved as-is (ChromaDB handles them)
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import chromadb
from chromadb.config import Settings

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "processed" / "embedded_chunks.json"
VECTORSTORE_DIR = BASE_DIR / "data" / "vectorstore"
LOGS_DIR = BASE_DIR / "logs"

COLLECTION_NAME = "hdfc_mutual_funds"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGS_DIR.mkdir(parents=True, exist_ok=True)
VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "vector_store.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Metadata sanitiser
# ---------------------------------------------------------------------------

def _sanitise_metadata(raw: dict) -> dict:
    """
    Convert chunk metadata to ChromaDB-safe types.

    Rules:
      - None  → ""  (ChromaDB rejects None values)
      - bool  → kept as bool  (ChromaDB supports bool natively)
      - str/int/float → kept as-is
      - enrichment_timestamp is kept for audit but not used in filtering
    """
    safe = {}
    for key, value in raw.items():
        if value is None:
            safe[key] = ""
        elif isinstance(value, bool):
            safe[key] = value          # native bool — ChromaDB handles it
        elif isinstance(value, (str, int, float)):
            safe[key] = value
        else:
            # Fallback: stringify anything unexpected (shouldn't happen)
            safe[key] = str(value)
    return safe


# ---------------------------------------------------------------------------
# ChromaDB client & collection
# ---------------------------------------------------------------------------

def get_or_create_collection(client: chromadb.PersistentClient) -> chromadb.Collection:
    """
    Get existing collection or create a fresh one.
    Uses cosine distance — correct for unit-normalised bge-small-en vectors.
    """
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},   # cosine distance for unit vectors
    )
    logger.info(
        f"Collection '{COLLECTION_NAME}' ready "
        f"(existing docs: {collection.count()})"
    )
    return collection


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def ingest(collection: chromadb.Collection, chunks: list[dict]) -> dict:
    """
    Upsert all chunks into the ChromaDB collection.

    Uses upsert (not add) so re-running is idempotent — existing chunk_ids
    are overwritten with fresh data rather than raising a duplicate error.

    Returns a summary dict with counts.
    """
    ids, embeddings, documents, metadatas = [], [], [], []

    for chunk in chunks:
        chunk_id = chunk["chunk_id"]
        text = chunk["text"]
        embedding = chunk["embedding"]
        raw_meta = chunk.get("metadata", {})

        # Add chunk_type to metadata so it's filterable in Phase 2.3
        raw_meta["chunk_type"] = chunk.get("chunk_type", "")
        raw_meta["token_count"] = chunk.get("token_count", 0)

        safe_meta = _sanitise_metadata(raw_meta)

        ids.append(chunk_id)
        embeddings.append(embedding)
        documents.append(text)
        metadatas.append(safe_meta)

    logger.info(f"Upserting {len(ids)} chunks into '{COLLECTION_NAME}'...")

    # Upsert in one batch (26 chunks is trivial)
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )

    final_count = collection.count()
    logger.info(f"Upsert complete. Collection now contains {final_count} documents.")

    return {
        "upserted": len(ids),
        "collection_count": final_count,
    }


# ---------------------------------------------------------------------------
# Smoke test — verify retrieval works
# ---------------------------------------------------------------------------

def _print_console_safe(text: str) -> None:
    """Avoid UnicodeEncodeError on Windows consoles (e.g. ₹ in chunk text)."""
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        safe = text.encode(enc, errors="replace").decode(enc, errors="replace")
    except (LookupError, UnicodeError):
        safe = text.encode("ascii", errors="replace").decode("ascii")
    print(safe)


def smoke_test(collection: chromadb.Collection) -> None:
    """
    Run 3 representative queries against the collection and print results.
    Uses the BGE query prefix on the query side.

    This validates that:
      1. The collection is queryable
      2. The top result is semantically correct
      3. Metadata (citation_text) is returned correctly
    """
    from sentence_transformers import SentenceTransformer

    BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
    MODEL_NAME = "BAAI/bge-small-en"

    logger.info("Running smoke test queries...")
    model = SentenceTransformer(MODEL_NAME)

    # Each test: (query_text, optional_metadata_filter)
    # Metadata filter is a ChromaDB `where` clause — used when the query
    # explicitly names a fund or chunk type, giving exact-match precision
    # on top of semantic similarity. Phase 2.3 applies this same pattern.
    test_queries = [
        (
            "What is the expense ratio of HDFC Mid Cap Fund?",
            {"$and": [{"scheme_name": {"$eq": "HDFC Mid Cap Fund Direct Growth"}},
                      {"chunk_type": {"$eq": "expense_ratio"}}]},
        ),
        (
            "What is the exit load for HDFC ELSS Tax Saver Fund?",
            {"$and": [{"scheme_name": {"$eq": "HDFC ELSS Tax Saver Fund Direct Plan Growth"}},
                      {"chunk_type": {"$eq": "exit_load"}}]},
        ),
        (
            "What is the minimum SIP amount for HDFC Large Cap Fund?",
            {"$and": [{"scheme_name": {"$eq": "HDFC Large Cap Fund Direct Growth"}},
                      {"chunk_type": {"$eq": "min_investment"}}]},
        ),
    ]

    _print_console_safe("\n" + "=" * 70)
    _print_console_safe("Smoke Test — Top-1 Retrieval Results (with metadata filter)")
    _print_console_safe("=" * 70)

    for query, where_filter in test_queries:
        prefixed = BGE_QUERY_PREFIX + query
        query_vec = model.encode(prefixed, normalize_embeddings=True).tolist()

        results = collection.query(
            query_embeddings=[query_vec],
            n_results=1,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        doc = results["documents"][0][0]
        meta = results["metadatas"][0][0]
        dist = results["distances"][0][0]
        similarity = 1 - dist   # cosine distance → cosine similarity

        _print_console_safe(f"\nQuery   : {query}")
        _print_console_safe(f"Score   : {similarity:.4f}  (cosine similarity)")
        _print_console_safe(f"Chunk   : [{meta.get('chunk_type')}] {meta.get('scheme_name')}")
        _print_console_safe(f"Answer  : {doc}")
        _print_console_safe(f"Citation: {meta.get('citation_text', '').split(chr(10))[0]}")

    _print_console_safe("\n" + "=" * 70)


# ---------------------------------------------------------------------------
# Persistence report
# ---------------------------------------------------------------------------

def save_store_manifest(chunks: list[dict], stats: dict) -> None:
    """
    Write a small manifest JSON alongside the vector store so other
    phases know what's in it without opening ChromaDB.
    """
    manifest = {
        "phase": "1.4_vector_storage",
        "description": "ChromaDB persistent vector store — HDFC Mutual Fund FAQ",
        "collection_name": COLLECTION_NAME,
        "vectorstore_path": str(VECTORSTORE_DIR),
        "embedding_model": "BAAI/bge-small-en",
        "embedding_dimension": 384,
        "distance_metric": "cosine",
        "total_documents": stats["collection_count"],
        "chunk_types": sorted({c["chunk_type"] for c in chunks}),
        "schemes": sorted({c["metadata"]["scheme_name"] for c in chunks}),
        "ingestion_timestamp": datetime.now().isoformat(),
        "query_prefix": (
            "Represent this sentence for searching relevant passages: <query>"
        ),
    }

    manifest_path = VECTORSTORE_DIR / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    logger.info(f"Manifest saved to: {manifest_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_vector_store() -> None:
    """
    Full Phase 1.4 vector storage pipeline:
      1. Load embedded_chunks.json
      2. Connect to / create ChromaDB persistent store
      3. Upsert all chunks (idempotent)
      4. Run smoke test to verify retrieval
      5. Save manifest
    """
    logger.info("=" * 60)
    logger.info("Phase 1.4 — Vector Storage (ChromaDB)")
    logger.info("=" * 60)

    if not INPUT_FILE.exists():
        logger.error(f"Input file not found: {INPUT_FILE}")
        logger.error("Run Phase 1.4 embedding first: python src/embedder.py")
        return

    # Load embedded chunks
    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    chunks: list[dict] = data.get("chunks", [])
    logger.info(f"Loaded {len(chunks)} embedded chunks from {INPUT_FILE.name}")

    # Connect to persistent ChromaDB
    logger.info(f"Connecting to ChromaDB at: {VECTORSTORE_DIR}")
    client = chromadb.PersistentClient(path=str(VECTORSTORE_DIR))

    # Get or create collection
    collection = get_or_create_collection(client)

    # Ingest
    stats = ingest(collection, chunks)

    # Save manifest
    save_store_manifest(chunks, stats)

    logger.info("=" * 60)
    logger.info(f"Vector store ready at : {VECTORSTORE_DIR}")
    logger.info(f"Collection            : {COLLECTION_NAME}")
    logger.info(f"Documents ingested    : {stats['upserted']}")
    logger.info(f"Total in collection   : {stats['collection_count']}")
    logger.info("=" * 60)

    # Smoke test
    smoke_test(collection)


if __name__ == "__main__":
    run_vector_store()
