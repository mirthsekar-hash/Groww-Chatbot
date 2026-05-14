"""
Phase 1.5 — Scheduled Data Refresh Pipeline Orchestrator

This script is the single entry point called by the GitHub Actions scheduler
(and usable locally) to run the full Phase 1.1 → 1.4 pipeline end-to-end.

Execution order:
    1.1  scraper.py          → data/raw/scraped_data.json
    1.2  chunker.py          → data/processed/chunks.json
    1.3  metadata_enricher.py → data/processed/enriched_chunks.json
    1.4a embedder.py         → data/processed/embedded_chunks.json
    1.4b vector_store.py     → data/vectorstore/

Failure handling (per phase_wise_architecture.md §1.5):
    - Each step is run as a subprocess.
    - If any step exits with a non-zero code, the pipeline halts immediately.
    - No subsequent steps are executed, so no partial/corrupt data is written.
    - The existing data files and vector store are left untouched on failure.
    - Exit code of this script mirrors the failing step's exit code, so
      GitHub Actions marks the workflow run as failed automatically.

Usage:
    python src/pipeline_runner.py              # full pipeline
    python src/pipeline_runner.py --dry-run    # print steps, do not execute
    python src/pipeline_runner.py --from 1.3   # resume from a specific step
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Pipeline step definitions
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

STEPS = [
    {
        "id": "1.1",
        "name": "Scrape",
        "description": "Re-scrape all 5 Groww URLs for latest fund data",
        "script": "src/scraper.py",
        "output": "data/raw/scraped_data.json",
    },
    {
        "id": "1.2",
        "name": "Chunk",
        "description": "Apply field-level semantic chunking to scraped data",
        "script": "src/chunker.py",
        "output": "data/processed/chunks.json",
    },
    {
        "id": "1.3",
        "name": "Enrich",
        "description": "Attach metadata (citation_text, is_elss, risk_level, etc.)",
        "script": "src/metadata_enricher.py",
        "output": "data/processed/enriched_chunks.json",
    },
    {
        "id": "1.4a",
        "name": "Embed",
        "description": "Generate 384-dim bge-small-en embeddings for all chunks",
        "script": "src/embedder.py",
        "output": "data/processed/embedded_chunks.json",
    },
    {
        "id": "1.4b",
        "name": "VectorStore",
        "description": "Upsert embeddings into ChromaDB (idempotent)",
        "script": "src/vector_store.py",
        "output": "data/vectorstore/manifest.json",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}", flush=True)


def _separator(char: str = "=", width: int = 60) -> None:
    print(char * width, flush=True)


def _run_step(step: dict, dry_run: bool) -> int:
    """
    Execute a single pipeline step as a subprocess.
    Returns the exit code (0 = success, non-zero = failure).
    """
    script_path = BASE_DIR / step["script"]
    cmd = [sys.executable, str(script_path)]

    _separator("-")
    _log(f"Step {step['id']} — {step['name']}")
    _log(f"  {step['description']}")
    _log(f"  Script : {step['script']}")
    _log(f"  Output : {step['output']}")

    if dry_run:
        _log("  [DRY RUN] Skipping execution.")
        return 0

    t0 = time.time()
    result = subprocess.run(cmd, cwd=str(BASE_DIR))
    elapsed = time.time() - t0

    if result.returncode == 0:
        _log(f"  [OK] Completed in {elapsed:.1f}s")
    else:
        _log(f"  [FAIL] FAILED (exit code {result.returncode}) after {elapsed:.1f}s")

    return result.returncode


def _verify_output(step: dict) -> bool:
    """
    Check that the expected output file exists after a step completes.
    Returns True if present, False if missing.
    """
    output_path = BASE_DIR / step["output"]
    if not output_path.exists():
        _log(f"  [FAIL] Expected output not found: {step['output']}")
        return False
    size_kb = output_path.stat().st_size / 1024
    _log(f"  [OK] Output verified: {step['output']} ({size_kb:.1f} KB)")
    return True


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 1.5 — Full data refresh pipeline runner"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print all steps without executing them",
    )
    parser.add_argument(
        "--from",
        dest="from_step",
        metavar="STEP_ID",
        default=None,
        help=(
            "Resume pipeline from a specific step ID "
            "(e.g. --from 1.3 skips 1.1 and 1.2). "
            f"Valid IDs: {[s['id'] for s in STEPS]}"
        ),
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_pipeline(dry_run: bool = False, from_step: str | None = None) -> int:
    """
    Execute the full Phase 1.1 → 1.4 pipeline.

    Args:
        dry_run:   If True, print steps without executing.
        from_step: Step ID to resume from (skips earlier steps).

    Returns:
        0 on full success, non-zero on first failure.
    """
    _separator()
    _log("Phase 1.5 — Scheduled Data Refresh Pipeline")
    _log(f"Mode     : {'DRY RUN' if dry_run else 'LIVE'}")
    _log(f"From step: {from_step or 'beginning'}")
    _log(f"Steps    : {len(STEPS)}")
    _separator()

    # Determine which steps to run
    step_ids = [s["id"] for s in STEPS]
    if from_step:
        if from_step not in step_ids:
            _log(f"ERROR: Unknown step ID '{from_step}'. Valid: {step_ids}")
            return 1
        start_idx = step_ids.index(from_step)
        steps_to_run = STEPS[start_idx:]
        _log(f"Resuming from step {from_step} — skipping {start_idx} earlier step(s)")
    else:
        steps_to_run = STEPS

    pipeline_start = time.time()
    completed = []
    failed_step = None

    for step in steps_to_run:
        exit_code = _run_step(step, dry_run)

        if exit_code != 0:
            failed_step = step
            break

        # Verify output file exists (skip in dry-run)
        if not dry_run and not _verify_output(step):
            failed_step = step
            break

        completed.append(step["id"])

    # --- Summary ---
    total_elapsed = time.time() - pipeline_start
    _separator()

    if failed_step:
        _log(f"PIPELINE FAILED at step {failed_step['id']} — {failed_step['name']}")
        _log(f"Completed steps : {completed}")
        _log(f"Elapsed         : {total_elapsed:.1f}s")
        _log("Existing data files are unchanged.")
        _separator()
        return 1

    _log(f"PIPELINE COMPLETE — all {len(steps_to_run)} steps succeeded")
    _log(f"Completed steps : {[s['id'] for s in steps_to_run]}")
    _log(f"Total elapsed   : {total_elapsed:.1f}s")
    _separator()
    return 0


if __name__ == "__main__":
    args = _parse_args()
    exit_code = run_pipeline(dry_run=args.dry_run, from_step=args.from_step)
    sys.exit(exit_code)
