"""
Phase 3 — Minimal web UI + HTTP API

Run (from repository root, after `pip install -r requirements.txt`):

    uvicorn src.chat_app:app --reload --host 127.0.0.1 --port 8000

Open http://127.0.0.1:8000 — legacy static UI under `web/`.

Next.js UI (recommended): from `frontend/` run `npm install && npm run dev`,
then open http://localhost:3000. Next proxies `/api/chat` and `/api/health` to this
server (`BACKEND_URL` in `frontend/.env.local` or default http://127.0.0.1:8000).
Run both processes in dev.

Environment: `GROQ_API_KEY` (and optional `GROQ_MODEL`) should be set;
optional `.env` is loaded on startup via python-dotenv.

Production (Railway / Vercel): set `PORT` via the platform. Restrict browser
origins with `CORS_ORIGINS` (comma-separated), e.g. your Vercel URL.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path

# Allow `uvicorn src.chat_app:app` from repo root: sibling modules live in `src/`.
_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from chat_pipeline import get_pipeline
from vector_store import bootstrap_vector_store, get_chroma_document_count

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"
STATIC_DIR = WEB_DIR / "static"

load_dotenv(BASE_DIR / ".env")


def _cors_allow_origins() -> list[str]:
    """
    Comma-separated allowlist from CORS_ORIGINS or CORS_ORIGIN (deployment.md).
    Empty or '*' → allow all origins (local dev). Production: set to your
    Vercel URL(s), e.g. https://your-app.vercel.app
    """
    raw = (os.environ.get("CORS_ORIGINS") or os.environ.get("CORS_ORIGIN") or "").strip()
    if not raw or raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)


class ChatResponse(BaseModel):
    reply: str


app = FastAPI(title="HDFC Mutual Fund FAQ Assistant", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    # `allow_credentials=True` is incompatible with wildcard origins in browsers.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _should_preload_embeddings() -> bool:
    explicit = os.environ.get("PRELOAD_MODEL", "").strip().lower()
    if explicit in ("0", "false", "no"):
        return False
    return True


def _preload_embeddings_background() -> None:
    """Warm BGE + Chroma in a daemon thread so deploy healthchecks stay fast."""
    if not _should_preload_embeddings():
        return

    def _run() -> None:
        try:
            get_pipeline().ensure_loaded()
            logger.info("Embedding model preloaded (background).")
        except Exception:
            logger.exception("Background embedding preload failed.")

    threading.Thread(target=_run, daemon=True, name="preload-embeddings").start()


@app.on_event("startup")
def _startup() -> None:
    try:
        count = bootstrap_vector_store(run_smoke_test=False)
        logger.info("ChromaDB ready with %s documents.", count)
    except Exception:
        logger.exception(
            "Vector store bootstrap failed; factual queries will error until "
            "data/processed/embedded_chunks.json is present."
        )

    _preload_embeddings_background()


@app.get("/api/health", response_model=None)
def health() -> JSONResponse:
    """
    Liveness check. Returns 503 when the vector store is empty (common on
    Railway before bootstrap from embedded_chunks.json).
    """
    doc_count = get_chroma_document_count()
    groq_ok = bool(os.environ.get("GROQ_API_KEY", "").strip())
    ready = doc_count > 0
    body = {
        "status": "ok" if ready else "degraded",
        "chroma_documents": doc_count,
        "groq_configured": groq_ok,
    }
    status_code = 200 if ready else 503
    return JSONResponse(status_code=status_code, content=body)


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    text = " ".join(req.message.strip().split())
    if not text:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        reply = get_pipeline().answer_query(text)
    except Exception:
        logger.exception("chat pipeline failure")
        raise HTTPException(status_code=503, detail="The assistant is temporarily unavailable.")

    return ChatResponse(reply=reply)


@app.get("/")
def index() -> FileResponse:
    index_path = WEB_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="web/index.html not found.")
    return FileResponse(index_path)


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
