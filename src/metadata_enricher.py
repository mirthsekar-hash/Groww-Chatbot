"""
Phase 1.3 - Metadata Enrichment
Reads data/processed/chunks.json, enriches each chunk's metadata with
additional fields required by the RAG pipeline, and writes the result to
data/processed/enriched_chunks.json.

Why enrichment matters
-----------------------
Phase 1.2 attached the minimum metadata needed to identify a chunk.
Phase 1.3 adds fields that the RAG pipeline (Phase 2) actively uses:

  amc_name          : Enables AMC-level filtering in the vector store.
  fund_category     : Enables category-level filtering (e.g. "Equity").
  fund_sub_category : Enables sub-category filtering (e.g. "Mid Cap").
  risk_level        : Riskometer classification — surfaced in responses.
  is_elss           : Boolean flag; routes ELSS-specific queries correctly.
  chunk_type_label  : Human-readable label used in response citations.
  citation_text     : Pre-built citation string appended to every response
                      by Phase 2.5 (e.g. "Source: HDFC Mid Cap Fund page
                      on Groww — https://groww.in/...").
  enrichment_timestamp : ISO timestamp of when enrichment ran.

The enricher reads fund-level data from scraped_data.json (the authoritative
source) and joins it onto each chunk by scheme_name, so no field is derived
from the chunk text itself — all values come from the original scraped record.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
CHUNKS_FILE = BASE_DIR / "data" / "processed" / "chunks.json"
SCRAPED_FILE = BASE_DIR / "data" / "raw" / "scraped_data.json"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "enriched_chunks.json"
LOGS_DIR = BASE_DIR / "logs"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "metadata_enricher.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chunk type → human-readable label mapping
# Used in citation_text and response formatting
# ---------------------------------------------------------------------------

CHUNK_TYPE_LABELS: dict[str, str] = {
    "overview":         "Fund Overview",
    "expense_ratio":    "Expense Ratio",
    "exit_load":        "Exit Load & Redemption",
    "min_investment":   "Minimum Investment",
    "benchmark":        "Benchmark Index",
    "elss_tax_benefit": "ELSS Tax Benefit & Lock-in",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_fund_lookup(scraped_data: dict) -> dict[str, dict]:
    """
    Build a dict keyed by scheme_name for O(1) lookup during enrichment.
    Falls back to source_url as secondary key in case scheme_name is missing.
    """
    lookup: dict[str, dict] = {}
    for fund in scraped_data.get("funds", []):
        name = fund.get("scheme_name")
        url = fund.get("source_url")
        if name:
            lookup[name] = fund
        if url:
            lookup[url] = fund  # secondary key
    return lookup


def _is_elss(fund: dict) -> bool:
    """Return True if the fund is an ELSS scheme."""
    category = (fund.get("category") or "").lower()
    sub_cat = (fund.get("sub_category") or "").lower()
    name = (fund.get("scheme_name") or "").lower()
    lock_in = fund.get("elss_lock_in_period")

    return (
        "elss" in category
        or "elss" in sub_cat
        or "elss" in name
        or "tax saver" in name
        or lock_in is not None
    )


def _build_citation_text(fund: dict, chunk_type: str) -> str:
    """
    Build the pre-formatted citation string for Phase 2.5.

    Format:
        Source: <Scheme Name> — <Chunk Type Label> | Groww
        <source_url>
        Last updated: <last_updated_date>

    This is the exact string Phase 2.5 appends to every response.
    """
    scheme_name = fund.get("scheme_name", "HDFC Mutual Fund Scheme")
    source_url = fund.get("source_url", "")
    last_updated = fund.get("last_updated_date", "Unknown")
    type_label = CHUNK_TYPE_LABELS.get(chunk_type, chunk_type.replace("_", " ").title())

    return (
        f"Source: {scheme_name} — {type_label} | Groww\n"
        f"{source_url}\n"
        f"Last updated from sources: {last_updated}"
    )


def _enrich_chunk(chunk: dict, fund_lookup: dict, enrichment_ts: str) -> dict:
    """
    Enrich a single chunk with fund-level metadata.

    Lookup order:
      1. scheme_name from chunk metadata  →  fund record
      2. source_url from chunk metadata   →  fund record (fallback)
      3. If neither matches, log a warning and return chunk with partial enrichment.
    """
    meta = chunk.get("metadata", {})
    scheme_name = meta.get("scheme_name")
    source_url = meta.get("source_url")
    chunk_type = chunk.get("chunk_type", "unknown")

    # Resolve fund record
    fund = fund_lookup.get(scheme_name) or fund_lookup.get(source_url)

    if not fund:
        logger.warning(
            f"No fund record found for chunk '{chunk.get('chunk_id')}' "
            f"(scheme='{scheme_name}', url='{source_url}'). "
            f"Enrichment will be partial."
        )
        # Still add timestamp and label so the chunk isn't malformed
        meta["chunk_type_label"] = CHUNK_TYPE_LABELS.get(chunk_type, chunk_type)
        meta["enrichment_timestamp"] = enrichment_ts
        chunk["metadata"] = meta
        return chunk

    # --- Core enrichment fields ---
    meta["amc_name"] = "HDFC Mutual Fund"
    meta["fund_category"] = fund.get("category")
    meta["fund_sub_category"] = fund.get("sub_category")
    meta["risk_level"] = fund.get("risk_level")
    meta["is_elss"] = _is_elss(fund)

    # --- Citation fields (used directly by Phase 2.5) ---
    meta["chunk_type_label"] = CHUNK_TYPE_LABELS.get(chunk_type, chunk_type.replace("_", " ").title())
    meta["citation_text"] = _build_citation_text(fund, chunk_type)

    # --- Audit field ---
    meta["enrichment_timestamp"] = enrichment_ts

    chunk["metadata"] = meta
    return chunk


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

REQUIRED_METADATA_FIELDS = [
    "source_url",
    "document_type",
    "scheme_name",
    "last_updated_date",
    "amc_name",
    "fund_category",
    "risk_level",
    "is_elss",
    "chunk_type_label",
    "citation_text",
    "enrichment_timestamp",
]


def _validate_chunk(chunk: dict) -> list[str]:
    """Return list of missing required metadata fields for a chunk."""
    meta = chunk.get("metadata", {})
    return [f for f in REQUIRED_METADATA_FIELDS if meta.get(f) is None]


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_enricher() -> None:
    """
    Load chunks.json + scraped_data.json, enrich all chunks, validate,
    and write enriched_chunks.json.
    """
    logger.info("=" * 60)
    logger.info("Phase 1.3 — Metadata Enrichment")
    logger.info("=" * 60)

    # --- Load inputs ---
    for path, label in [(CHUNKS_FILE, "chunks.json"), (SCRAPED_FILE, "scraped_data.json")]:
        if not path.exists():
            logger.error(f"{label} not found at: {path}")
            logger.error("Run previous phases first.")
            return

    with open(CHUNKS_FILE, encoding="utf-8") as f:
        chunks_data = json.load(f)

    with open(SCRAPED_FILE, encoding="utf-8") as f:
        scraped_data = json.load(f)

    chunks: list[dict] = chunks_data.get("chunks", [])
    logger.info(f"Loaded {len(chunks)} chunks from {CHUNKS_FILE.name}")
    logger.info(f"Loaded {len(scraped_data.get('funds', []))} fund records from {SCRAPED_FILE.name}")

    # --- Build lookup ---
    fund_lookup = _build_fund_lookup(scraped_data)
    logger.info(f"Fund lookup built: {len(fund_lookup)} keys")

    # --- Enrich ---
    enrichment_ts = datetime.now().isoformat()
    enriched: list[dict] = []
    validation_warnings = 0

    for chunk in chunks:
        enriched_chunk = _enrich_chunk(chunk, fund_lookup, enrichment_ts)

        # Validate
        missing = _validate_chunk(enriched_chunk)
        if missing:
            logger.warning(
                f"Chunk '{enriched_chunk.get('chunk_id')}' "
                f"({enriched_chunk.get('chunk_type')}) missing fields: {missing}"
            )
            validation_warnings += 1

        enriched.append(enriched_chunk)

    # --- Build output ---
    output = {
        "metadata": {
            "phase": "1.3",
            "description": "Metadata-enriched chunks ready for vector embedding",
            "source_chunks_file": str(CHUNKS_FILE),
            "source_scraped_file": str(SCRAPED_FILE),
            "total_chunks": len(enriched),
            "validation_warnings": validation_warnings,
            "enrichment_timestamp": enrichment_ts,
            "metadata_fields_added": [
                "amc_name",
                "fund_category",
                "fund_sub_category",
                "risk_level",
                "is_elss",
                "chunk_type_label",
                "citation_text",
                "enrichment_timestamp",
            ],
        },
        "chunks": enriched,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info("=" * 60)
    logger.info(f"Enrichment complete. Output saved to: {OUTPUT_FILE}")
    logger.info(f"Total chunks enriched : {len(enriched)}")
    logger.info(f"Validation warnings   : {validation_warnings}")
    logger.info("=" * 60)

    _print_summary(enriched)


def _print_summary(chunks: list[dict]) -> None:
    """Print a per-chunk enrichment summary to stdout."""
    print("\n" + "=" * 70)
    print("Enrichment Summary")
    print("=" * 70)
    print(f"{'Scheme':<35} {'Type':<20} {'ELSS':>5} {'Risk':<15}")
    print("-" * 70)

    for chunk in chunks:
        meta = chunk.get("metadata", {})
        scheme = (meta.get("scheme_name") or "").replace("HDFC ", "").replace(" Direct", "").replace(" Growth", "")
        ctype = chunk.get("chunk_type", "")
        is_elss = "Yes" if meta.get("is_elss") else "No"
        risk = (meta.get("risk_level") or "N/A").replace(" Risk", "")
        print(f"{scheme:<35} {ctype:<20} {is_elss:>5} {risk:<15}")

    print("=" * 70)

    # Show a sample citation_text for one chunk
    if chunks:
        sample = chunks[0]
        print("\nSample citation_text (chunk 0):")
        print("-" * 70)
        print(sample["metadata"].get("citation_text", "N/A"))
        print("=" * 70)


if __name__ == "__main__":
    run_enricher()
