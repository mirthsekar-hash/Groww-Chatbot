"""
Phase 1.1 - Scrape Output Validator
Reads data/raw/scraped_data.json and prints a validation report.

Usage:
    python src/validate_scrape.py
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "data" / "raw" / "scraped_data.json"

MANDATORY_FIELDS = [
    "scheme_name",
    "category",
    "sub_category",
    "risk_level",
    "nav",
    "min_sip_amount",
    "min_lumpsum_amount",
    "aum",
    "expense_ratio",
    "exit_load",
    "benchmark_index",
    "fund_managers",
    "last_updated_date",
    "source_url",
]

ELSS_SCHEME_KEYWORDS = ["elss", "tax saver"]


def validate() -> None:
    if not OUTPUT_FILE.exists():
        print(f"[ERROR] Output file not found: {OUTPUT_FILE}")
        print("Run 'python src/scraper.py' first.")
        return

    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    meta = data.get("metadata", {})
    funds = data.get("funds", [])

    print("=" * 60)
    print("Phase 1.1 — Scrape Validation Report")
    print("=" * 60)
    print(f"Run timestamp : {meta.get('run_timestamp', 'N/A')}")
    print(f"Total URLs    : {meta.get('total_urls', 0)}")
    print(f"Successful    : {meta.get('successful_scrapes', 0)}")
    print(f"Failed        : {meta.get('failed_scrapes', 0)}")
    print()

    all_passed = True

    for fund in funds:
        name = fund.get("scheme_name") or fund.get("source_url")
        status = fund.get("scrape_status", "unknown")
        errors = fund.get("scrape_errors", [])

        print(f"  Fund : {name}")
        print(f"  URL  : {fund.get('source_url')}")
        print(f"  Status: {status.upper()}")

        # Check mandatory fields
        missing = [f for f in MANDATORY_FIELDS if not fund.get(f)]
        if missing:
            print(f"  [WARN] Missing fields: {missing}")
            all_passed = False
        else:
            print("  [OK] All mandatory fields present")

        # ELSS-specific check
        is_elss = any(kw in (name or "").lower() for kw in ELSS_SCHEME_KEYWORDS)
        if is_elss:
            lock_in = fund.get("elss_lock_in_period")
            if lock_in:
                print(f"  [OK] ELSS lock-in period: {lock_in}")
            else:
                print("  [WARN] ELSS lock-in period not found")
                all_passed = False

        # Scrape errors
        if errors:
            for err in errors:
                print(f"  [ERR] {err}")

        print()

    print("=" * 60)
    if all_passed:
        print("VALIDATION PASSED — All records complete.")
    else:
        print("VALIDATION WARNINGS — Some fields are missing. Check logs/scraper.log.")
    print("=" * 60)


if __name__ == "__main__":
    validate()
