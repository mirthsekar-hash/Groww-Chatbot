"""Lightweight timing helpers (set PERF_LOG=1 to log stage durations)."""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def perf_enabled() -> bool:
    return os.environ.get("PERF_LOG", "").strip().lower() in ("1", "true", "yes")


@contextmanager
def perf_span(label: str):
    if not perf_enabled():
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms = (time.perf_counter() - t0) * 1000
        logger.info("perf %s: %.0fms", label, ms)
