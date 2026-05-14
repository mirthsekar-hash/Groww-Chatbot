"""
Phase 1.4 (Embedding only) — Dense Vector Embedding
Reads data/processed/enriched_chunks.json, generates a 384-dim embedding
for each chunk using BAAI/bge-small-en, and saves the result to
data/processed/embedded_chunks.json.

Model: BAAI/bge-small-en
  - 384-dimensional output vectors
  - Retrieval-optimised (trained on MS MARCO with contrastive learning)
  - Runs fully offline on CPU after first download (~130 MB)
  - Max 512 tokens — all our chunks are 22–85 tokens, well within limit

BGE query prefix rule (applied in Phase 2.3, NOT here):
  Documents (chunks) are embedded as-is.
  Queries must be prefixed with:
    "Represent this sentence for searching relevant passages: <query>"
  This file only handles document-side embedding.

Output schema per chunk:
  All existing fields from enriched_chunks.json are preserved.
  One new field is added:
    embedding: List[float]  — 384-dim unit-normalised vector
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "processed" / "enriched_chunks.json"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "embedded_chunks.json"
LOGS_DIR = BASE_DIR / "logs"

# BGE-small-en: retrieval-optimised, 384-dim, ~130MB, CPU-friendly
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en"

# Embed all chunks in a single batch (26 chunks is trivial for this model)
BATCH_SIZE = 32

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "embedder.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def load_model() -> SentenceTransformer:
    """
    Load BAAI/bge-small-en.
    Downloads ~130MB on first run, then uses the local cache.
    """
    logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
    t0 = time.time()
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    elapsed = time.time() - t0
    logger.info(f"Model loaded in {elapsed:.1f}s")
    logger.info(f"Embedding dimension: {model.get_sentence_embedding_dimension()}")
    return model


def embed_chunks(chunks: list[dict], model: SentenceTransformer) -> list[dict]:
    """
    Generate embeddings for all chunks and attach them in-place.

    Documents are embedded WITHOUT the BGE query prefix — the prefix is
    only applied to user queries at retrieval time (Phase 2.3).

    normalize_embeddings=True produces unit vectors, which makes cosine
    similarity equivalent to dot product — faster and numerically stable.
    """
    texts = [chunk["text"] for chunk in chunks]

    logger.info(f"Embedding {len(texts)} chunks (batch_size={BATCH_SIZE})...")
    t0 = time.time()

    vectors = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,   # unit vectors → cosine sim = dot product
        show_progress_bar=True,
        convert_to_numpy=True,
    )

    elapsed = time.time() - t0
    logger.info(f"Embedding complete in {elapsed:.2f}s  ({len(texts)/elapsed:.1f} chunks/sec)")

    # Attach embedding to each chunk
    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector.tolist()   # JSON-serialisable list of floats

    return chunks


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

EXPECTED_DIM = 384


def validate_embeddings(chunks: list[dict]) -> list[str]:
    """
    Sanity-check every embedding:
      - Correct dimension (384)
      - No NaN or Inf values
      - Approximately unit-normalised (L2 norm ≈ 1.0)
    Returns a list of error strings (empty = all good).
    """
    import math
    errors = []

    for i, chunk in enumerate(chunks):
        vec = chunk.get("embedding")
        cid = chunk.get("chunk_id", f"index_{i}")

        if vec is None:
            errors.append(f"[{cid}] Missing embedding")
            continue

        if len(vec) != EXPECTED_DIM:
            errors.append(f"[{cid}] Wrong dimension: {len(vec)} (expected {EXPECTED_DIM})")

        if any(math.isnan(v) or math.isinf(v) for v in vec):
            errors.append(f"[{cid}] Contains NaN or Inf values")

        norm = math.sqrt(sum(v * v for v in vec))
        if not (0.99 < norm < 1.01):
            errors.append(f"[{cid}] L2 norm out of range: {norm:.4f} (expected ~1.0)")

    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_embedder() -> None:
    """
    Load enriched chunks → embed with bge-small-en → validate → save.
    """
    logger.info("=" * 60)
    logger.info("Phase 1.4 — Embedding (BAAI/bge-small-en)")
    logger.info("=" * 60)

    if not INPUT_FILE.exists():
        logger.error(f"Input file not found: {INPUT_FILE}")
        logger.error("Run Phase 1.3 first: python src/metadata_enricher.py")
        return

    # Load
    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    chunks: list[dict] = data.get("chunks", [])
    logger.info(f"Loaded {len(chunks)} enriched chunks from {INPUT_FILE.name}")

    # Load model
    model = load_model()

    # Embed
    chunks = embed_chunks(chunks, model)

    # Validate
    errors = validate_embeddings(chunks)
    if errors:
        for err in errors:
            logger.error(f"Validation error: {err}")
        logger.error(f"{len(errors)} validation error(s) found. Check output carefully.")
    else:
        logger.info("Validation passed — all embeddings are well-formed.")

    # Build output
    output = {
        "metadata": {
            "phase": "1.4_embedding",
            "description": "Chunks with bge-small-en embeddings (384-dim, unit-normalised)",
            "embedding_model": EMBEDDING_MODEL_NAME,
            "embedding_dimension": EXPECTED_DIM,
            "normalised": True,
            "bge_query_prefix": (
                "Represent this sentence for searching relevant passages: "
                "<query>  ← apply this prefix to user queries in Phase 2.3"
            ),
            "total_chunks": len(chunks),
            "validation_errors": len(errors),
            "source_file": str(INPUT_FILE),
            "run_timestamp": datetime.now().isoformat(),
        },
        "chunks": chunks,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info("=" * 60)
    logger.info(f"Output saved to : {OUTPUT_FILE}")
    logger.info(f"Total chunks    : {len(chunks)}")
    logger.info(f"Embedding dim   : {EXPECTED_DIM}")
    logger.info(f"Validation errors: {len(errors)}")
    logger.info("=" * 60)

    _print_summary(chunks)


def _print_summary(chunks: list[dict]) -> None:
    """Print a compact per-chunk embedding summary."""
    import math

    print("\n" + "=" * 65)
    print("Embedding Summary")
    print("=" * 65)
    print(f"{'Scheme':<35} {'Type':<20} {'Dim':>5} {'Norm':>6}")
    print("-" * 65)

    for chunk in chunks:
        meta = chunk.get("metadata", {})
        scheme = (meta.get("scheme_name") or "").replace("HDFC ", "").replace(" Direct", "").replace(" Growth", "")
        ctype = chunk.get("chunk_type", "")
        vec = chunk.get("embedding", [])
        dim = len(vec)
        norm = math.sqrt(sum(v * v for v in vec)) if vec else 0.0
        print(f"{scheme:<35} {ctype:<20} {dim:>5} {norm:>6.4f}")

    print("=" * 65)


if __name__ == "__main__":
    run_embedder()
