# Phase 1 Edge Cases: Data Ingestion & Knowledge Base Preparation

This document identifies potential edge cases and failure modes during the data collection and processing phase.

| Edge Case | Description | Mitigation Strategy |
| :--- | :--- | :--- |
| **URL Unavailability** | One of the 5 mandatory Groww URLs is down (404, 503) or blocked. | Implement retry logic and alert if mandatory sources are unreachable. |
| **Scraping Selector Failure** | Groww changes its website structure, breaking CSS selectors/XPath. | Use robust selectors and implement validation checks to ensure data is actually being captured. |
| **Missing Factual Fields** | A specific fund page is missing a mandatory field (e.g., "Min SIP Amount" is not listed). | Design the schema to handle null values and log missing mandatory information. |
| **Date Parsing Error** | The "Last Updated" date on the page is missing or in an unrecognized format. | Use flexible date parsers; default to "Unknown" or the crawl date if parsing fails. |
| **Token Limit Overflow** | The text content of a page exceeds the embedding model's maximum token limit. | Implement a chunking strategy that respects token limits while preserving semantic meaning. |
| **Duplicate Content** | The same factual information appears in multiple places on a page (e.g., summary and details). | Use de-duplication techniques or hashing during the ingestion process. |
| **Dynamic Content** | Crucial data is loaded via JavaScript after the initial page load. | Use a headless browser (like Playwright/Puppeteer) if static scraping is insufficient. |
