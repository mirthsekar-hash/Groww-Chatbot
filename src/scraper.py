"""
Phase 1.1 - Data Sourcing & Collection
Scrapes factual mutual fund data from the 5 mandatory Groww URLs.

Usage:
    python src/scraper.py

Output:
    data/raw/scraped_data.json
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError  # noqa: F401

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MANDATORY_URLS = [
    "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth",
    "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
]

# Delay between requests to avoid rate limiting (seconds)
REQUEST_DELAY = 2

# Playwright page load timeout (milliseconds)
PAGE_TIMEOUT = 30_000

# Directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = BASE_DIR / "data" / "raw"
LOGS_DIR = BASE_DIR / "logs"

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

LOGS_DIR.mkdir(parents=True, exist_ok=True)
DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "scraper.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    """Strip whitespace and normalise unicode spaces."""
    return re.sub(r"\s+", " ", text).strip() if text else ""


def _extract_scheme_name(soup: BeautifulSoup) -> str | None:
    """Extract the fund scheme name from the <h1> tag."""
    h1 = soup.find("h1")
    return _clean(h1.get_text()) if h1 else None


def _extract_category_risk(soup: BeautifulSoup) -> dict:
    """
    Extract category, sub-category, and risk level.
    On Groww pages these appear as pill/badge links near the top of the page.
    Example: Equity | Mid Cap | Very High Risk
    """
    result = {"category": None, "sub_category": None, "risk_level": None}

    # The category pills are anchor tags with filter URLs
    cat_links = soup.find_all("a", href=re.compile(r"/mutual-funds/filter\?"))
    labels = [_clean(a.get_text()) for a in cat_links if a.get_text(strip=True)]

    for label in labels:
        lower = label.lower()
        if "risk" in lower:
            result["risk_level"] = label
        elif result["category"] is None:
            result["category"] = label
        else:
            result["sub_category"] = label

    return result


def _extract_nav(soup: BeautifulSoup) -> str | None:
    """
    Extract the latest NAV value.
    Groww renders NAV in a paragraph that contains 'NAV:' text.
    """
    # Look for text containing NAV pattern like "NAV: 11 May '26₹221.26"
    nav_pattern = re.compile(r"NAV[:\s]+.*?₹([\d,]+\.?\d*)", re.IGNORECASE)
    page_text = soup.get_text(" ", strip=True)
    match = nav_pattern.search(page_text)
    if match:
        return f"₹{match.group(1)}"

    # Fallback: look for a span/div near "NAV" label
    for tag in soup.find_all(string=re.compile(r"^NAV$", re.IGNORECASE)):
        parent = tag.parent
        if parent:
            sibling_text = _clean(parent.get_text())
            rupee_match = re.search(r"₹([\d,]+\.?\d*)", sibling_text)
            if rupee_match:
                return f"₹{rupee_match.group(1)}"
    return None


def _extract_min_sip(soup: BeautifulSoup) -> str | None:
    """
    Extract minimum SIP investment amount.
    Appears in the 'Minimum investments' section as 'Min. for SIP ₹XXX'.
    """
    page_text = soup.get_text(" ", strip=True)

    # Pattern: "Min. for SIP ₹100"
    match = re.search(r"Min\.?\s+for\s+SIP\s+(₹[\d,]+)", page_text, re.IGNORECASE)
    if match:
        return match.group(1)

    # Fallback: "Minimum SIP Investment is set to ₹XXX"
    match = re.search(r"Minimum SIP Investment is set to (₹[\d,]+)", page_text, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def _extract_min_lumpsum(soup: BeautifulSoup) -> str | None:
    """Extract minimum lumpsum (one-time) investment amount."""
    page_text = soup.get_text(" ", strip=True)

    # Pattern: "Min. for 1st investment ₹100"
    match = re.search(r"Min\.?\s+for\s+1st\s+investment\s+(₹[\d,]+)", page_text, re.IGNORECASE)
    if match:
        return match.group(1)

    # Fallback: "Minimum Lumpsum Investment is ₹XXX"
    match = re.search(r"Minimum Lumpsum Investment is (₹[\d,]+)", page_text, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def _extract_aum(soup: BeautifulSoup) -> str | None:
    """
    Extract Fund Size (AUM).
    Appears as 'Fund size (AUM) ₹XX,XXX.XX Cr' near the top summary.
    """
    page_text = soup.get_text(" ", strip=True)

    match = re.search(r"Fund size \(AUM\)\s*(₹[\d,]+\.?\d*\s*Cr)", page_text, re.IGNORECASE)
    if match:
        return match.group(1)

    # Fallback: "AUM of ₹XX,XXX Cr"
    match = re.search(r"AUM[^\₹]*?(₹[\d,]+\.?\d*\s*Cr)", page_text, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def _extract_expense_ratio(soup: BeautifulSoup) -> str | None:
    """
    Extract expense ratio percentage.
    Appears as 'Expense ratio X.XX%' in the top summary section.
    """
    page_text = soup.get_text(" ", strip=True)

    # Pattern: "Expense ratio 0.72%"
    match = re.search(r"Expense ratio\s*[\s\S]{0,30}?(\d+\.\d+%)", page_text, re.IGNORECASE)
    if match:
        return match.group(1)

    # Fallback: "Expense Ratio of HDFC ... is X.XX%"
    match = re.search(r"Expense Ratio of [^.]+? is (\d+\.\d+%)", page_text, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def _extract_exit_load(soup: BeautifulSoup) -> str | None:
    """
    Extract exit load details from the 'Exit load, stamp duty and tax' section.
    Captures only the current/active exit load rule (first match).
    """
    page_text = soup.get_text(" ", strip=True)

    # Nil exit load (ELSS funds)
    if re.search(r"\bnil\b.*?exit load|exit load.*?\bnil\b", page_text, re.IGNORECASE):
        return "Nil"

    # Pattern: "Exit load of X% if redeemed within Y year(s)." — take only the first match
    match = re.search(
        r"Exit load of (\d+(?:\.\d+)?%\s+if\s+redeemed\s+within\s+\d+\s+year[s]?\.?)",
        page_text,
        re.IGNORECASE,
    )
    if match:
        return _clean(f"Exit load of {match.group(1)}")

    return None


def _extract_benchmark(soup: BeautifulSoup) -> str | None:
    """
    Extract the benchmark index.
    Appears as 'Fund benchmark NIFTY ...' in the Investment Objective section.
    """
    page_text = soup.get_text(" ", strip=True)

    # Match "Fund benchmark NIFTY 500 Total Return Index" — stop at next sentence/section
    match = re.search(
        r"Fund benchmark\s+((?:NIFTY|BSE|SENSEX|S&P)[^S][^\n]{3,60}?)(?:\s+Scheme|\s+Fund house|\s{3,}|$)",
        page_text,
    )
    if match:
        return _clean(match.group(1))

    return None


def _extract_fund_managers(soup: BeautifulSoup) -> list[str]:
    """
    Extract fund manager names.
    Groww shows them in 'Fund management' section with name + date range.
    """
    managers = []
    page_text = soup.get_text(" ", strip=True)

    # Pattern: "CS Chirag Setalvad Jan 2013 - Present"
    # Names appear before a month-year pattern
    matches = re.findall(
        r"([A-Z]{2}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+\w{3}\s+\d{4}\s+-\s+(?:Present|\w{3}\s+\d{4})",
        page_text,
    )
    for m in matches:
        # Strip the 2-letter prefix (initials abbreviation used by Groww)
        name = re.sub(r"^[A-Z]{2}\s+", "", m)
        if name not in managers:
            managers.append(name)

    return managers


def _extract_elss_lock_in(soup: BeautifulSoup, scheme_name: str) -> str | None:
    """
    For ELSS funds, extract the lock-in period.
    ELSS funds have a mandatory 3-year lock-in under Section 80C.
    """
    if "elss" not in scheme_name.lower() and "tax saver" not in scheme_name.lower():
        return None

    page_text = soup.get_text(" ", strip=True)
    match = re.search(r"lock.in[^.]*?(\d+[\s-]+year[s]?)", page_text, re.IGNORECASE)
    if match:
        return match.group(0)

    # ELSS always has 3-year lock-in — note it explicitly if not found on page
    return "3 years (mandatory under Section 80C)"


def _extract_last_updated(crawl_date: str) -> str:
    """
    Groww pages show NAV date (e.g., 'NAV: 11 May '26').
    We use the crawl date as the authoritative last_updated_date for metadata.
    """
    return crawl_date


# ---------------------------------------------------------------------------
# Core scraping function
# ---------------------------------------------------------------------------

def scrape_fund_page(url: str, page) -> dict:
    """
    Scrape a single Groww mutual fund page and return structured data.

    Args:
        url:  The Groww fund page URL.
        page: A Playwright Page object.

    Returns:
        A dict with all extracted fields and metadata.
    """
    crawl_date = datetime.now().strftime("%Y-%m-%d")
    result = {
        "source_url": url,
        "document_type": "fund_page",
        "scheme_name": None,
        "category": None,
        "sub_category": None,
        "risk_level": None,
        "nav": None,
        "min_sip_amount": None,
        "min_lumpsum_amount": None,
        "aum": None,
        "expense_ratio": None,
        "exit_load": None,
        "benchmark_index": None,
        "fund_managers": [],
        "elss_lock_in_period": None,
        "last_updated_date": crawl_date,
        "scrape_status": "success",
        "scrape_errors": [],
    }

    try:
        logger.info(f"Fetching: {url}")
        page.goto(url, wait_until="networkidle", timeout=PAGE_TIMEOUT)

        # Wait for the main fund title to be present
        page.wait_for_selector("h1", timeout=PAGE_TIMEOUT)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        # --- Extract each field with individual error handling ---
        def safe_extract(field_name: str, extractor_fn, *args):
            try:
                value = extractor_fn(*args)
                result[field_name] = value
                if value is None:
                    logger.warning(f"[{url}] Missing field: {field_name}")
                    result["scrape_errors"].append(f"Missing field: {field_name}")
            except Exception as exc:
                logger.error(f"[{url}] Error extracting {field_name}: {exc}")
                result["scrape_errors"].append(f"Error extracting {field_name}: {exc}")

        safe_extract("scheme_name", _extract_scheme_name, soup)

        cat_risk = _extract_category_risk(soup)
        result["category"] = cat_risk["category"]
        result["sub_category"] = cat_risk["sub_category"]
        result["risk_level"] = cat_risk["risk_level"]

        safe_extract("nav", _extract_nav, soup)
        safe_extract("min_sip_amount", _extract_min_sip, soup)
        safe_extract("min_lumpsum_amount", _extract_min_lumpsum, soup)
        safe_extract("aum", _extract_aum, soup)
        safe_extract("expense_ratio", _extract_expense_ratio, soup)
        safe_extract("exit_load", _extract_exit_load, soup)
        safe_extract("benchmark_index", _extract_benchmark, soup)
        safe_extract("fund_managers", _extract_fund_managers, soup)

        scheme_name = result.get("scheme_name") or url
        safe_extract("elss_lock_in_period", _extract_elss_lock_in, soup, scheme_name)

        logger.info(
            f"Scraped '{result['scheme_name']}' — "
            f"{len(result['scrape_errors'])} missing/error fields"
        )

    except PlaywrightTimeoutError:
        msg = f"Timeout loading page: {url}"
        logger.error(msg)
        result["scrape_status"] = "timeout"
        result["scrape_errors"].append(msg)

    except Exception as exc:
        msg = f"Unexpected error scraping {url}: {exc}"
        logger.error(msg)
        result["scrape_status"] = "error"
        result["scrape_errors"].append(msg)

    return result


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

MANDATORY_FIELDS = [
    "scheme_name",
    "category",
    "risk_level",
    "min_sip_amount",
    "expense_ratio",
    "exit_load",
    "benchmark_index",
]


def validate_record(record: dict) -> list[str]:
    """Return a list of missing mandatory fields for a scraped record."""
    missing = []
    for field in MANDATORY_FIELDS:
        if not record.get(field):
            missing.append(field)
    return missing


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_scraper() -> None:
    """
    Orchestrate scraping of all 5 mandatory URLs and save output to JSON.
    """
    logger.info("=" * 60)
    logger.info("Phase 1.1 — Data Sourcing & Collection")
    logger.info(f"Target URLs: {len(MANDATORY_URLS)}")
    logger.info("=" * 60)

    all_records = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        for i, url in enumerate(MANDATORY_URLS):
            record = scrape_fund_page(url, page)

            # Validate mandatory fields
            missing = validate_record(record)
            if missing:
                logger.warning(
                    f"Record for '{record.get('scheme_name', url)}' "
                    f"is missing mandatory fields: {missing}"
                )

            all_records.append(record)

            # Polite delay between requests (skip after last URL)
            if i < len(MANDATORY_URLS) - 1:
                logger.info(f"Waiting {REQUEST_DELAY}s before next request...")
                time.sleep(REQUEST_DELAY)

        context.close()
        browser.close()

    # --- Save output ---
    output = {
        "metadata": {
            "phase": "1.1",
            "description": "Data Sourcing & Collection — HDFC Mutual Fund schemes",
            "amc": "HDFC Mutual Fund",
            "total_urls": len(MANDATORY_URLS),
            "successful_scrapes": sum(1 for r in all_records if r["scrape_status"] == "success"),
            "failed_scrapes": sum(1 for r in all_records if r["scrape_status"] != "success"),
            "run_timestamp": datetime.now().isoformat(),
        },
        "funds": all_records,
    }

    output_path = DATA_RAW_DIR / "scraped_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info("=" * 60)
    logger.info(f"Scraping complete. Output saved to: {output_path}")
    logger.info(
        f"Results: {output['metadata']['successful_scrapes']} success, "
        f"{output['metadata']['failed_scrapes']} failed"
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    run_scraper()
