"""
Phase 1.2 - Data Parsing & Chunking
Reads data/raw/scraped_data.json and produces semantically meaningful chunks
ready for embedding in Phase 1.4.

Chunking Strategy: Field-Level Semantic Sectioning
---------------------------------------------------
Rather than blindly splitting text by character count, each chunk represents
ONE factual topic for ONE fund (e.g., "exit load for HDFC Mid Cap Fund").
This gives the retriever precise, non-ambiguous context to match against a
user query like "What is the exit load for HDFC Mid Cap?"

Chunk types produced per fund:
  - overview        : name, category, risk, AUM, NAV, fund managers
  - expense_ratio   : expense ratio fact
  - exit_load       : exit load rule (+ ELSS lock-in if applicable)
  - min_investment  : minimum SIP and lumpsum amounts
  - benchmark       : benchmark index
  - elss_tax        : ELSS-specific lock-in and tax benefit (ELSS funds only)

Each chunk carries full metadata for Phase 1.3:
  source_url, document_type, scheme_name, last_updated_date, chunk_type,
  chunk_id (SHA-256 hash for deduplication), token_count

Edge cases handled (per phase1_edge_cases.md):
  - Token Limit Overflow : chunks are validated against MAX_TOKENS (512)
  - Duplicate Content    : SHA-256 hash deduplication across all chunks
  - Missing Fields       : null fields are skipped; chunk is omitted if its
                           core value is missing
"""

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "raw" / "scraped_data.json"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "chunks.json"
LOGS_DIR = BASE_DIR / "logs"

# Approximate token limit for embedding models (e.g. text-embedding-ada-002
# supports 8191 tokens; we keep chunks well under 512 for focused retrieval)
MAX_TOKENS = 512

# Rough token estimator: 1 token ≈ 4 characters (conservative for English)
CHARS_PER_TOKEN = 4

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "chunker.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _estimate_tokens(text: str) -> int:
    """Rough token count estimate: len(text) / CHARS_PER_TOKEN."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def _chunk_id(text: str, scheme_name: str, chunk_type: str) -> str:
    """
    Deterministic SHA-256 hash used for deduplication.
    Keyed on scheme_name + chunk_type ONLY (not text content) so the ID
    is stable across refreshes — the same fund+type always gets the same
    ID, enabling true upsert behaviour in ChromaDB on every pipeline run.
    """
    raw = f"{scheme_name}::{chunk_type}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _make_chunk(
    text: str,
    chunk_type: str,
    fund: dict,
) -> dict | None:
    """
    Build a single chunk dict with full metadata.
    Returns None if text is empty or exceeds MAX_TOKENS (safety guard).
    """
    text = text.strip()
    if not text:
        return None

    token_count = _estimate_tokens(text)
    if token_count > MAX_TOKENS:
        logger.warning(
            f"Chunk '{chunk_type}' for '{fund['scheme_name']}' "
            f"exceeds MAX_TOKENS ({token_count} > {MAX_TOKENS}). Skipping."
        )
        return None

    scheme_name = fund.get("scheme_name", "Unknown")
    return {
        "chunk_id": _chunk_id(text, scheme_name, chunk_type),
        "chunk_type": chunk_type,
        "text": text,
        # --- Phase 1.3 metadata (attached here, enriched further in 1.3) ---
        "metadata": {
            "source_url": fund.get("source_url"),
            "document_type": fund.get("document_type", "fund_page"),
            "scheme_name": scheme_name,
            "last_updated_date": fund.get("last_updated_date"),
        },
        "token_count": token_count,
    }


# ---------------------------------------------------------------------------
# Per-field chunk builders
# ---------------------------------------------------------------------------

def _chunk_overview(fund: dict) -> dict | None:
    """
    Overview chunk: identity, category, risk, AUM, NAV, fund managers.
    This is the 'who is this fund' chunk — answers broad questions.
    """
    parts = []

    name = fund.get("scheme_name")
    if not name:
        return None

    parts.append(f"{name} is an {fund.get('category', 'Equity')} mutual fund"
                 f" in the {fund.get('sub_category', 'N/A')} sub-category"
                 f" offered by HDFC Mutual Fund.")

    risk = fund.get("risk_level")
    if risk:
        parts.append(f"The fund is classified as {risk} on the riskometer.")

    aum = fund.get("aum")
    if aum:
        parts.append(f"The fund's Assets Under Management (AUM) is {aum}.")

    nav = fund.get("nav")
    if nav:
        parts.append(f"The latest NAV is {nav}.")

    managers = fund.get("fund_managers")
    if managers:
        mgr_str = " and ".join(managers)
        parts.append(f"The fund is managed by {mgr_str}.")

    return _make_chunk(" ".join(parts), "overview", fund)


def _chunk_expense_ratio(fund: dict) -> dict | None:
    """
    Expense ratio chunk: single focused fact.
    """
    expense_ratio = fund.get("expense_ratio")
    if not expense_ratio:
        return None

    name = fund.get("scheme_name", "This fund")
    text = (
        f"The expense ratio of {name} is {expense_ratio}. "
        f"This is the annual fee charged by HDFC Mutual Fund for managing the scheme."
    )
    return _make_chunk(text, "expense_ratio", fund)


def _chunk_exit_load(fund: dict) -> dict | None:
    """
    Exit load chunk: redemption penalty rule.
    For ELSS funds, also includes the lock-in period since they are related.
    """
    exit_load = fund.get("exit_load")
    if not exit_load:
        return None

    name = fund.get("scheme_name", "This fund")
    # Normalise trailing punctuation — avoid double periods
    exit_load_clean = exit_load.rstrip(".")
    parts = [f"Exit load for {name}: {exit_load_clean}."]

    # Append ELSS lock-in here since it directly affects redemption
    lock_in = fund.get("elss_lock_in_period")
    if lock_in:
        parts.append(
            f"Additionally, as an ELSS fund, investments are subject to a "
            f"mandatory lock-in period of {lock_in}. "
            f"Redemption is not permitted before the lock-in period ends."
        )

    return _make_chunk(" ".join(parts), "exit_load", fund)


def _chunk_min_investment(fund: dict) -> dict | None:
    """
    Minimum investment chunk: SIP and lumpsum amounts.
    """
    sip = fund.get("min_sip_amount")
    lumpsum = fund.get("min_lumpsum_amount")

    if not sip and not lumpsum:
        return None

    name = fund.get("scheme_name", "This fund")
    parts = [f"Minimum investment details for {name}:"]

    if sip:
        parts.append(f"The minimum SIP (Systematic Investment Plan) amount is {sip} per month.")
    if lumpsum:
        parts.append(f"The minimum one-time (lumpsum) investment amount is {lumpsum}.")

    return _make_chunk(" ".join(parts), "min_investment", fund)


def _chunk_benchmark(fund: dict) -> dict | None:
    """
    Benchmark chunk: index the fund is measured against.
    """
    benchmark = fund.get("benchmark_index")
    if not benchmark:
        return None

    name = fund.get("scheme_name", "This fund")
    text = (
        f"The benchmark index for {name} is {benchmark}. "
        f"Fund performance is evaluated relative to this index."
    )
    return _make_chunk(text, "benchmark", fund)


def _chunk_elss_tax(fund: dict) -> dict | None:
    """
    ELSS-specific chunk: tax benefit under Section 80C and lock-in details.
    Only produced for ELSS funds.
    """
    lock_in = fund.get("elss_lock_in_period")
    if not lock_in:
        return None  # Not an ELSS fund

    name = fund.get("scheme_name", "This fund")
    text = (
        f"{name} is an Equity Linked Savings Scheme (ELSS) that qualifies for "
        f"tax deduction under Section 80C of the Income Tax Act, up to ₹1.5 lakh per year. "
        f"It has a mandatory lock-in period of {lock_in}. "
        f"The exit load is Nil since redemption before lock-in expiry is not permitted."
    )
    return _make_chunk(text, "elss_tax_benefit", fund)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _deduplicate(chunks: list[dict]) -> tuple[list[dict], int]:
    """
    Remove duplicate chunks by chunk_id (SHA-256 hash).
    Returns (deduplicated_list, number_of_duplicates_removed).
    """
    seen: set[str] = set()
    unique: list[dict] = []
    duplicates = 0

    for chunk in chunks:
        cid = chunk["chunk_id"]
        if cid in seen:
            duplicates += 1
            logger.debug(f"Duplicate chunk removed: {cid} ({chunk['chunk_type']})")
        else:
            seen.add(cid)
            unique.append(chunk)

    return unique, duplicates


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

CHUNK_BUILDERS = [
    _chunk_overview,
    _chunk_expense_ratio,
    _chunk_exit_load,
    _chunk_min_investment,
    _chunk_benchmark,
    _chunk_elss_tax,
]


def run_chunker() -> None:
    """
    Read scraped_data.json, produce semantic chunks, deduplicate, and save.
    """
    logger.info("=" * 60)
    logger.info("Phase 1.2 — Data Parsing & Chunking")
    logger.info("=" * 60)

    if not INPUT_FILE.exists():
        logger.error(f"Input file not found: {INPUT_FILE}")
        logger.error("Run Phase 1.1 scraper first: python src/scraper.py")
        return

    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    funds = data.get("funds", [])
    logger.info(f"Loaded {len(funds)} fund records from {INPUT_FILE.name}")

    all_chunks: list[dict] = []
    skipped_funds = 0

    for fund in funds:
        name = fund.get("scheme_name", fund.get("source_url"))
        status = fund.get("scrape_status")

        if status != "success":
            logger.warning(f"Skipping '{name}' — scrape status: {status}")
            skipped_funds += 1
            continue

        fund_chunks: list[dict] = []
        for builder in CHUNK_BUILDERS:
            chunk = builder(fund)
            if chunk:
                fund_chunks.append(chunk)
            # If chunk is None, the field was missing — already logged in scraper

        logger.info(f"  '{name}' → {len(fund_chunks)} chunks produced")
        all_chunks.extend(fund_chunks)

    # Deduplication
    all_chunks, n_dupes = _deduplicate(all_chunks)
    if n_dupes:
        logger.info(f"Deduplication: removed {n_dupes} duplicate chunk(s)")

    # Token overflow summary
    total_tokens = sum(c["token_count"] for c in all_chunks)
    max_chunk_tokens = max((c["token_count"] for c in all_chunks), default=0)

    # Build output
    output = {
        "metadata": {
            "phase": "1.2",
            "description": "Semantic field-level chunks for RAG embedding",
            "chunking_strategy": "field_level_semantic_sectioning",
            "source_file": str(INPUT_FILE),
            "total_funds_processed": len(funds) - skipped_funds,
            "total_funds_skipped": skipped_funds,
            "total_chunks": len(all_chunks),
            "duplicates_removed": n_dupes,
            "total_estimated_tokens": total_tokens,
            "max_chunk_tokens": max_chunk_tokens,
            "max_tokens_limit": MAX_TOKENS,
            "run_timestamp": datetime.now().isoformat(),
        },
        "chunks": all_chunks,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info("=" * 60)
    logger.info(f"Chunking complete. Output saved to: {OUTPUT_FILE}")
    logger.info(f"Total chunks : {len(all_chunks)}")
    logger.info(f"Total tokens : ~{total_tokens} (estimated)")
    logger.info(f"Largest chunk: ~{max_chunk_tokens} tokens")
    logger.info(f"Duplicates   : {n_dupes} removed")
    logger.info("=" * 60)

    # Print a human-readable summary table
    _print_summary(all_chunks)


def _print_summary(chunks: list[dict]) -> None:
    """Print a per-fund, per-chunk-type summary table to stdout."""
    print("\n" + "=" * 60)
    print("Chunk Summary")
    print("=" * 60)
    print(f"{'Fund':<45} {'Type':<20} {'Tokens':>6}")
    print("-" * 60)

    for chunk in chunks:
        fund_name = chunk["metadata"]["scheme_name"]
        # Shorten long names for display
        short_name = fund_name.replace("HDFC ", "").replace(" Direct", "").replace(" Growth", "")
        print(f"{short_name:<45} {chunk['chunk_type']:<20} {chunk['token_count']:>6}")

    print("=" * 60)


if __name__ == "__main__":
    run_chunker()
