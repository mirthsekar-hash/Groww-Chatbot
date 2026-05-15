# deployment.md

# Groww RAG Chatbot — Deployment Guide

This document explains how to deploy the Groww RAG Chatbot application.

Deployment Stack:

* Frontend → Vercel
* Backend → Railway

---

# Architecture Overview

Frontend:

* React / Next.js application
* Hosted on Vercel

Backend:

* FastAPI / Node.js API server
* Handles:

  * RAG pipeline
  * Vector search
  * LLM orchestration
  * Document ingestion
  * Authentication
* Hosted on Railway

Database / Storage (Optional):

* PostgreSQL
* Pinecone / Weaviate / ChromaDB
* Redis
* Object storage for PDFs

---

# Repository layout (this project)

Monorepo — **not** a separate `backend/` folder:

```text
project-root/
├── frontend/           # Next.js (Vercel root directory)
├── src/                # FastAPI app (`src.chat_app:app`)
├── requirements.txt
├── Procfile            # Railway / process start (also see railway.toml)
├── railway.toml        # Railway deploy + healthcheck
├── nixpacks.toml       # Python 3.11 for Nixpacks
└── deployment.md
```

---

# Frontend Deployment (Vercel)

## Step 1 — Push Code to GitHub

Push the frontend project to GitHub.

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin <github_repo_url>
git push -u origin main
```

---

# Step 2 — Create Vercel Project

1. Go to:
   https://vercel.com

2. Login using GitHub.

3. Click:
   "Add New Project"

4. Import the frontend repository.

5. Configure:

   * Framework Preset → **Next.js**
   * **Root Directory → `frontend`** (required — do not leave as `.` / repo root)

   If Root Directory is the repo root, Vercel scans `requirements.txt` and `src/*.py` and tries to deploy **FastAPI** on Vercel, which fails with:

   `No FastAPI entrypoint found in standard locations...`

   The API belongs on **Railway** only; Vercel should host **`frontend/`** only.

6. After changing Root Directory, **Redeploy** (Settings → General → Root Directory → Save, then Deployments → Redeploy).

---

# Step 3 — Add Environment Variables

In Vercel dashboard:

Settings → Environment Variables

Add (production):

```env
BACKEND_URL=https://your-backend-url.up.railway.app
```

`BACKEND_URL` is read **on the server** by Next.js route handlers (`app/api/*/route.ts`) when proxying to FastAPI — it is **not** exposed to the browser.

Optional alias (same value; only if you prefer the name from older drafts):

```env
NEXT_PUBLIC_API_URL=https://your-backend-url.up.railway.app
```

Optional:

```env
NEXT_PUBLIC_ENV=production
NEXT_PUBLIC_SENTRY_DSN=
NEXT_PUBLIC_ANALYTICS_ID=
```

---

# Step 4 — Deploy Frontend

Click:
"Deploy"

Vercel automatically:

* Builds the app
* Deploys globally
* Generates production URL

Example:

```bash
https://groww-rag-chatbot.vercel.app
```

---

# Frontend Build Configuration

## Recommended package.json scripts

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  }
}
```

---

# Backend Deployment (Railway)

## Step 1 — Prepare Backend

Ensure backend contains:

### FastAPI start command (this repo)

From the **repository root** (Railway / Docker):

```bash
python -m uvicorn src.chat_app:app --host 0.0.0.0 --port $PORT
```

`Procfile` and `railway.toml` already use this command; `$PORT` is injected by Railway.

### Example Node.js Start Command

```bash
npm run start
```

---

# Step 2 — Push Backend to GitHub

Push the **same** GitHub repository used for Vercel (monorepo).

---

# Step 3 — Create Railway Project

1. Go to:
   https://railway.app

2. Login with GitHub.

3. Click:
   "New Project"

4. Select:
   "Deploy from GitHub Repo"

5. Choose this GitHub repository.

6. Set **Root Directory** to the **repository root** (leave empty / `.`) — **not** `frontend/`. The Python service lives next to `requirements.txt`.

7. Do **not** add a root `package.json` with a `build` script — Railway will try to run `next build` and fail with `next: not found`. Only **Vercel** builds `frontend/`.

---

# Step 4 — Configure Environment Variables

Inside Railway dashboard:

Variables → Add Variables

Example (required for factual chat — **not** on Vercel):

```env
GROQ_API_KEY=your_groq_key
GROQ_MODEL=llama-3.3-70b-versatile
ENVIRONMENT=production
# Comma-separated browser origins (your Vercel deployment URL(s))
CORS_ORIGINS=https://groww-chatbot-kappa.vercel.app
```

The API **bootstraps ChromaDB on startup** from `data/processed/embedded_chunks.json` (the sqlite file is not in git). After deploy, open `https://<your-railway-domain>/api/health` — expect `{"status":"ok","chroma_documents":26,"groq_configured":true}`.

Optional: `PRELOAD_MODEL=true` to load the embedding model at boot (uses more RAM; default is **off** on Railway/production).

Optional (not required for the current FAQ stack):

```env
OPENAI_API_KEY=
DATABASE_URL=
REDIS_URL=
JWT_SECRET=
```

---

# Step 5 — Configure Build & Start Commands

## Python / FastAPI

Build Command:

```bash
pip install -r requirements.txt
```

Start Command (already in `railway.toml` / `Procfile`):

```bash
python -m uvicorn src.chat_app:app --host 0.0.0.0 --port $PORT
```

---

## Node.js

Build Command:

```bash
npm install
```

Start Command:

```bash
npm run start
```

---

# Step 6 — Deploy Backend

Railway automatically:

* Builds container
* Assigns domain
* Deploys API

Example:

```bash
https://groww-rag-api.up.railway.app
```

---

# Enable CORS

Backend must allow frontend domain.

This backend reads **`CORS_ORIGINS`** (comma-separated) or **`CORS_ORIGIN`** (single URL). Example:

```env
CORS_ORIGINS=https://groww-rag-chatbot.vercel.app,https://www.your-domain.com
```

Unset or `*` keeps permissive `allow_origins=["*"]` for local development. The app uses `allow_credentials=False` (no cookie session on this API).

---

# Production Environment Variables

## Frontend (Vercel → Environment Variables)

```env
BACKEND_URL=https://your-service.up.railway.app
```

Example for this project: `BACKEND_URL` = your Railway public URL (no trailing slash). Without this, the UI at [groww-chatbot-kappa.vercel.app](https://groww-chatbot-kappa.vercel.app/) cannot reach the API.

---

## Backend (Railway → Variables)

```env
GROQ_API_KEY=
CORS_ORIGINS=https://groww-rag-chatbot.vercel.app
```

---

# Deployment Workflow

## Frontend

```bash
git push origin main
```

Vercel automatically redeploys.

---

## Backend

```bash
git push origin main
```

Railway automatically redeploys.

---

# Recommended Production Stack

Frontend:

* Next.js
* TailwindCSS
* Vercel

Backend:

* FastAPI or Express.js
* LangChain / LlamaIndex
* Railway

Vector Database:

* Pinecone
* ChromaDB
* Weaviate

LLM Providers:

* OpenAI
* Groq
* Anthropic

---

# Recommended Security Checklist

## Frontend

* Never expose API secrets
* Use `BACKEND_URL` for the FastAPI base URL (server-side on Vercel). Avoid putting secrets in `NEXT_PUBLIC_*`.

## Backend

* Store secrets in Railway variables
* Enable rate limiting
* Validate uploaded files
* Add request logging
* Use HTTPS only

---

# Monitoring

Recommended:

* Sentry
* Railway Metrics
* Vercel Analytics
* PostHog

---

# Recommended CI/CD Flow

```text
GitHub Push
    ↓
Automatic Deploy
    ↓
Railway Backend Deployment
    ↓
Vercel Frontend Deployment
    ↓
Production Live
```

---

# Common Deployment Issues

## CORS Error

Fix:

* Add Vercel domain to backend CORS config

---

## Build Failure

Fix:

* Ensure correct root directory
* Ensure package.json exists
* Verify requirements.txt exists

---

## Railway: `next: not found` / `npm run build --prefix frontend`

**Cause:** Railway detected a root **`package.json`** and tried to build the Next.js app. The frontend belongs on **Vercel** only.

**Fix:** **No** root `package.json`. Redeploy the Railway service (not Vercel).

---

## Railway: `pip install` exit code **127**

**Cause:** Custom `buildCommand` or Nixpacks `[phases.install]` ran `pip` before Python was on `PATH`.

**Fix:** Use the repo’s minimal `nixpacks.toml` (only `NIXPACKS_PYTHON_VERSION`) and **no** `buildCommand` in `railway.toml` — Nixpacks auto-installs from `requirements.txt`.

---

## `No FastAPI entrypoint found` on Vercel

**Cause:** Vercel project **Root Directory** is the repository root (`.`), not `frontend/`. Vercel auto-detects Python and looks for `app.py`, while this repo’s API is `src/chat_app.py` and is meant for **Railway**.

**Fix:**

1. Vercel → your project → **Settings** → **General** → **Root Directory** → set to **`frontend`** → **Save**.
2. **Redeploy** the latest commit.
3. Do **not** deploy the FastAPI app on Vercel; use **Railway** with `python -m uvicorn src.chat_app:app` (see Backend Deployment above).

Root `vercel.json` sets `"rootDirectory": "frontend"` for Vercel. Railway uses `railway.toml` + `nixpacks.toml` for **Python only** (`pip install -r requirements.txt`).

---

## Environment Variables Not Loading

Fix:

* Redeploy after adding variables
* Ensure correct variable names

---

# Final Production URLs

Frontend:

```bash
https://groww-rag-chatbot.vercel.app
```

Backend:

```bash
https://groww-rag-api.up.railway.app
```

---

# Future Improvements

* Dockerize backend
* Add Kubernetes support
* Add CDN caching
* Add queue workers
* Add AI streaming responses
* Add observability stack
* Add autoscaling
* Add authentication

---

# Deployment Complete

The Groww RAG Chatbot is now production-ready using:

* Vercel for frontend hosting
* Railway for backend hosting
* GitHub-based CI/CD workflow
