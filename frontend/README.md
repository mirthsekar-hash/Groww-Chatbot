# HDFC FAQ — Next.js UI

Matches **Groww RAG Dark** from `screens/stitch_groww_ai_research_terminal/` (tokens in `DESIGN.md`, layout inspired by `code.html`).

## Prereqs

- Node.js 18+ and npm  
- Python FastAPI backend on **port 8000** (see repo root `src/chat_app.py`)

## Run

Terminal 1 — API:

```bash
cd ..
python -m uvicorn src.chat_app:app --host 127.0.0.1 --port 8000
```

Terminal 2 — Next (`app/api/chat` and `app/api/health` proxy to FastAPI):

```bash
npm install
npm run dev
```

Open **http://localhost:3000**.  
Optional: copy `.env.example` to `.env.local` and set `BACKEND_URL` if the API is not at `http://127.0.0.1:8000`.

## Build

```bash
npm run build && npm start
```
