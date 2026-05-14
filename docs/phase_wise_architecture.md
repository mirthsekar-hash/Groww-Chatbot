# Phase-Wise Architecture: Mutual Fund FAQ Assistant

This document outlines the phase-wise architecture and implementation plan for building the Facts-Only Mutual Fund FAQ Assistant, based on the requirements defined in the problem statement.

## Phase 1: Data Ingestion & Knowledge Base Preparation
The foundational phase focuses on collecting, processing, and storing official mutual fund data to be used by the RAG system.

*   **1.1 Data Sourcing & Collection (Strict Restriction):**
    *   **Target AMC:** HDFC Mutual Fund.
    *   **Mandatory Sources:** Use ONLY the following Groww URLs for data ingestion. No other sources or external URLs are permitted for this project:
        *   https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth
        *   https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth
        *   https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth
        *   https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth
        *   https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth
    *   **Action:** Scrape and extract factual data (Expense Ratio, Exit Load, Min SIP, Riskometer, etc.) directly from these specific pages.
*   **1.2 Data Parsing & Chunking:**
    *   Parse text from varied formats (PDFs, HTML).
    *   Apply a chunking strategy (e.g., recursive character splitting or semantic sectioning) to break documents into digestible pieces for the LLM.
*   **1.3 Metadata Enrichment:**
    *   Attach critical metadata to each chunk: `source_url`, `document_type`, `scheme_name`, and `last_updated_date`. This is essential for the strict citation requirements.
*   **1.4 Embedding & Vector Storage:**
    *   Convert text chunks into dense vector embeddings using an embedding model.
    *   Ingest embeddings and metadata into a Vector Database (e.g., ChromaDB, Pinecone, or FAISS) for efficient semantic search.
*   **1.5 Scheduled Data Refresh:**
    *   Mutual fund data (NAV, expense ratio, exit load, AUM) changes periodically. A scheduled pipeline re-runs Phases 1.1 → 1.4 automatically to keep the knowledge base current.
    *   **Scheduler:** GitHub Actions `schedule` trigger using cron syntax.
    *   **Refresh Frequency:** Daily at 09:15 IST (GitHub Actions cron `45 3 * * *`, i.e. 03:45 UTC).
    *   **Pipeline Steps Executed on Schedule:**
        1.  `python src/scraper.py` — re-scrape all 5 Groww URLs for latest field values.
        2.  `python src/chunker.py` — re-chunk the updated scraped data.
        3.  `python src/metadata_enricher.py` — re-enrich chunks with updated `last_updated_date`.
        4.  `python src/embedder.py` — re-embed updated chunks with `BAAI/bge-small-en`.
        5.  `python src/vector_store.py` — upsert updated embeddings into ChromaDB (idempotent).
    *   **Artifact Persistence:** Updated `data/` files (raw JSON, processed chunks, embedded chunks) are committed back to the repository by the workflow, providing a full audit trail of each refresh run.
    *   **Failure Handling:** If any pipeline step fails (e.g., Groww URL unavailable), the workflow exits with a non-zero code, GitHub marks the run as failed, and the existing vector store is left untouched — no partial or corrupt data is written.

## Phase 2: RAG Pipeline & Backend Services
This phase builds the core retrieval and generation logic, incorporating strict compliance guardrails.

*   **2.1 Query Processing & Privacy Filter:**
    *   Receive user query.
    *   **Guardrail:** Reject or anonymize queries containing PII (PAN, Aadhaar, account numbers, email, phone).
*   **2.2 Intent Classification & Refusal Handling:**
    *   Classify the query intent (Factual vs. Advisory/Speculative).
    *   **Guardrail:** If the query asks for investment advice, performance comparisons, or predictions, bypass retrieval and route to a static refusal template providing a polite decline and an AMFI/SEBI educational link.
*   **2.3 Semantic Retrieval (Metadata-Filtered):**
    *   **Strategy:** Metadata-Filtered Semantic Retrieval — combines bge-small-en vector similarity with ChromaDB `where` clause filtering on `scheme_name` and `chunk_type`. This is required because 4 of 5 funds share near-identical `exit_load` and `min_investment` chunk text; pure semantic search cannot reliably distinguish them.
    *   **Stage 1 — Entity Extraction:** Parse the user query using a keyword alias map to extract:
        *   `fund_name` — matched against fund aliases (e.g., "mid cap" → `"HDFC Mid Cap Fund Direct Growth"`, "elss" / "tax saver" → `"HDFC ELSS Tax Saver Fund Direct Plan Growth"`).
        *   `topic` — mapped to a `chunk_type` (e.g., "expense ratio" → `expense_ratio`, "sip" / "minimum" → `min_investment`, "80c" → `elss_tax_benefit`, "lock-in" → `exit_load`).
    *   **Stage 2 — ChromaDB Query (3-tier fallback):**
        *   **Tier 1** — Both `fund_name` and `topic` extracted: apply `where` filter on both `scheme_name` and `chunk_type`, `n_results=1`. Highest precision.
        *   **Tier 2** — Only `fund_name` extracted: apply `where` filter on `scheme_name` only, `n_results=3`, semantic similarity ranks the correct topic chunk.
        *   **Tier 3** — Neither extracted (generic query): pure semantic search across full collection, `n_results=3`.
    *   **BGE Query Prefix:** All query embeddings are prefixed with `"Represent this sentence for searching relevant passages: "` before encoding (document embeddings are stored without this prefix).
    *   **Alias Maps (fixed vocabulary — no NLP model required):**
        ```
        FUND_ALIASES  : "mid cap" → HDFC Mid Cap Fund Direct Growth
                        "flexi cap" → HDFC Flexi Cap Direct Plan Growth
                        "focused" → HDFC Focused Fund Direct Growth
                        "elss" / "tax saver" → HDFC ELSS Tax Saver Fund Direct Plan Growth
                        "large cap" → HDFC Large Cap Fund Direct Growth

        TOPIC_ALIASES : "expense ratio" → expense_ratio
                        "exit load" → exit_load
                        "sip" / "minimum" → min_investment
                        "benchmark" → benchmark
                        "riskometer" / "risk" / "aum" / "nav" → overview
                        "lock-in" → exit_load
                        "80c" / "tax" → elss_tax_benefit
        ```
*   **2.4 Prompt Assembly & LLM Generation:**
    *   Construct a strict prompt injecting the user query and retrieved context.
    *   **Prompt Constraints:** Enforce a maximum of 3 sentences, strictly factual tone, and no extrapolations.
    *   Invoke the Large Language Model (LLM) to generate the response based *only* on the provided context.
*   **2.5 Response Formatting:**
    *   Post-process the LLM output to append the required footer: `"Last updated from sources: <date>"` and strictly one citation link retrieved from the chunk metadata.

## Phase 3: Minimal User Interface
Developing the lightweight, user-facing component of the assistant.

*   **3.1 UI Framework:**
    *   Implement a simple chat interface (e.g., using React, Streamlit, Gradio, or Vanilla HTML/JS).
*   **3.2 Core UI Elements:**
    *   **Welcome Message & Examples:** Display a standard greeting and three clickable example queries (e.g., "What is the exit load for [Scheme]?", "What is the riskometer rating?").
    *   **Disclaimer:** Display a prominent, persistent disclaimer: `"Facts-only. No investment advice."`
*   **3.3 API Integration:**
    *   Connect the UI to the backend RAG pipeline to send queries and receive formatted responses.

## Phase 4: Testing, Validation & Deployment
Ensuring the system adheres to all constraints and success criteria before delivery.

*   **4.1 Accuracy & Retrieval Testing:**
    *   Test the system with various factual queries to ensure correct context retrieval and accurate answers.
*   **4.2 Guardrail & Compliance Testing:**
    *   Adversarial testing with advisory, performance-seeking, and PII-laden queries to guarantee proper refusal handling and zero data storage violations.
*   **4.3 Output Constraint Validation:**
    *   Automated checks to ensure all responses are ≤ 3 sentences, contain exactly one valid source link, and include the proper footer.
*   **4.4 Documentation & Handoff:**
    *   Finalize the `README.md` with setup instructions, selected AMC/schemes, architecture overview, and known limitations.

## Phase 5: Scheduled Data Refresh via GitHub Actions
This phase automates the end-to-end data refresh pipeline so the knowledge base stays current without manual intervention.

*   **5.1 Workflow Trigger:**
    *   **File:** `.github/workflows/refresh_data.yml`
    *   **Schedule:** `cron: '45 3 * * *'` — daily at 03:45 UTC (09:15 IST).
    *   **Manual Trigger:** `workflow_dispatch` is also enabled, allowing an on-demand refresh from the GitHub Actions UI at any time (e.g., after a known Groww page update).

*   **5.2 Workflow Steps:**
    ```
    Checkout repo
        ↓
    Set up Python 3.11
        ↓
    Install dependencies (pip install -r requirements.txt)
        ↓
    Install Playwright Chromium (python -m playwright install chromium)
        ↓
    Run scraper          → data/raw/scraped_data.json
        ↓
    Run chunker          → data/processed/chunks.json
        ↓
    Run metadata enricher → data/processed/enriched_chunks.json
        ↓
    Run embedder         → data/processed/embedded_chunks.json
        ↓
    Run vector store     → data/vectorstore/
        ↓
    Commit & push updated data/ files back to repository
    ```

*   **5.3 GitHub Actions Configuration:**
    *   **Runner:** `ubuntu-latest` (Linux runner — no Windows-specific dependencies).
    *   **Python version:** 3.11 (stable, pre-built wheels available for all dependencies).
    *   **Secrets required:** None for scraping. If the repo is private, `GITHUB_TOKEN` (auto-provided) is sufficient for the commit-back step.
    *   **Commit message format:** `chore: scheduled data refresh — <YYYY-MM-DD>` for clear audit trail in git history.
    *   **Concurrency guard:** `concurrency: group: data-refresh` with `cancel-in-progress: false` — prevents two refresh runs from colliding and corrupting the vector store.

*   **5.4 Failure & Alerting Strategy:**
    *   If any pipeline step exits with a non-zero code, the workflow fails immediately (subsequent steps are skipped).
    *   The existing `data/` files and vector store are **not overwritten** on failure — the last successful refresh remains active.
    *   GitHub sends an automatic email notification to repository owners on workflow failure.
    *   Workflow run logs are retained for 30 days in the GitHub Actions tab for post-mortem debugging.

*   **5.5 Data Versioning:**
    *   Each successful refresh produces a git commit containing the updated `data/raw/scraped_data.json`, `data/processed/*.json`, and `data/vectorstore/manifest.json`.
    *   The `data/vectorstore/chroma.sqlite3` binary is excluded from git (added to `.gitignore`) and rebuilt from the committed JSON files on each run — keeping the repository lightweight.
    *   The `manifest.json` `ingestion_timestamp` field serves as the authoritative record of when data was last refreshed, and is surfaced in the `"Last updated from sources: <date>"` footer on every chatbot response.
