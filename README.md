# Mutual Fund FAQ Assistant - Phase 1.1 Implementation

## Prerequisites

**Python 3.8+ is required but not currently installed on this system.**

### Install Python
1. Download Python from [python.org](https://www.python.org/downloads/)
2. During installation, check "Add Python to PATH"
3. Verify installation: `python --version`

## Phase 1.1: Data Sourcing & Collection

This implementation scrapes factual data from the 5 mandatory Groww URLs for HDFC Mutual Fund schemes.

### Setup Instructions

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the scraper:**
   ```bash
   python src/scraper.py
   ```

3. **Output:**
   - Raw scraped data: `data/raw/scraped_data.json`
   - Logs: `logs/scraper.log`

### Selected AMC and Schemes

**AMC:** HDFC Mutual Fund

**Schemes:**
1. HDFC Mid Cap Fund Direct Growth
2. HDFC Equity Fund Direct Growth (Flexi Cap)
3. HDFC Focused Fund Direct Growth
4. HDFC ELSS Tax Saver Fund Direct Plan Growth
5. HDFC Large Cap Fund Direct Growth

### Data Fields Extracted

For each scheme, the scraper extracts:
- Scheme Name
- Category & Sub-category
- Risk Level (Riskometer)
- NAV (Net Asset Value)
- Minimum SIP Amount
- Minimum Lumpsum Investment
- Fund Size (AUM)
- Expense Ratio
- Exit Load Details
- Benchmark Index
- Fund Managers
- Last Updated Date
- Source URL

### Architecture Overview

```
Phase 1.1 Data Collection
├── Web Scraping (Playwright - headless browser)
├── Data Extraction (BeautifulSoup4)
├── Data Validation & Error Handling
└── JSON Output with Metadata
```

### Known Limitations

- Requires JavaScript rendering (uses Playwright)
- Dependent on Groww's website structure
- Rate limiting: 2-second delay between requests
- No retry logic for failed requests (will be added in Phase 1.2)

### Disclaimer

**Facts-only. No investment advice.**

This tool collects publicly available factual information about mutual fund schemes. It does not provide investment recommendations or advice.
