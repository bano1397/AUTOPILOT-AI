# Deploying AutoPilot AI (100% free stack)

This deploys the whole platform to always-on free services. **Authentication is
disabled** — the app opens straight into a shared public workspace, so anyone
with the link can use it (perfect for a portfolio demo).

## Architecture

| Piece | Service | Free tier | Cost |
|---|---|---|---|
| Frontend (Next.js) | **Vercel** | Hobby | $0 |
| Backend (FastAPI) | **Render** (Docker web service) | Free | $0 |
| Database | **Neon** (Postgres) | Free | $0 |
| Vector store | **Qdrant Cloud** | Free 1 GB | $0 |
| LLM | **Groq** (Llama, OpenAI-compatible) | Free | $0 |
| Embeddings | **Jina AI** | Free | $0 |

> Ollama/ChromaDB/SQLite (the local stack) are replaced by Groq/Qdrant/Postgres
> in the cloud — selected purely by environment variables, no code change. Run
> locally exactly as before with `docker compose up`.

## What you do vs. what's already done

Already in the repo: cloud provider adapters, `$PORT`-portable backend image,
`render.yaml`, and env templates (`*/.env.production.example`).

You need to (I can't create accounts or push to your GitHub for you):
create the free accounts below, push this repo to GitHub, paste the env values,
and click deploy.

---

## Step 1 — Push to GitHub
```bash
cd "D:/AutoPilot AI"
git init && git add -A && git commit -m "AutoPilot AI"
git branch -M main
git remote add origin https://github.com/<you>/autopilot-ai.git
git push -u origin main
```
A `.gitignore` should exclude `.env`, `node_modules`, `.next`, `*.db`, `.venv`.

## Step 2 — Provision the free backing services (collect the keys)
1. **Neon** (neon.tech) → new project → copy the **asyncpg** connection string.
   Make it: `postgresql+asyncpg://USER:PASSWORD@HOST/neondb?ssl=require`
2. **Qdrant Cloud** (cloud.qdrant.io) → free cluster → copy its **URL** + **API key**.
3. **Groq** (console.groq.com) → API Keys → copy `GROQ_API_KEY`.
4. **Jina** (jina.ai → API) → copy `JINA_API_KEY`.

## Step 3 — Backend on Render
1. Render → **New → Blueprint** → pick your GitHub repo (it reads `render.yaml`).
2. In the service's **Environment** tab, set the `sync: false` secrets:
   `DATABASE_URL`, `GROQ_API_KEY`, `JINA_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`,
   and `CORS_ORIGINS` (set after Step 4 — your Vercel URL).
3. Deploy. On boot it runs `alembic upgrade head` against Neon, then serves on
   Render's injected `$PORT`. Verify: open `https://<svc>.onrender.com/health` → `{"status":"ok"}`.

## Step 4 — Frontend on Vercel
1. Vercel → **Add New → Project** → import the repo → **Root Directory = `frontend`**.
2. Environment variable: `NEXT_PUBLIC_API_URL = https://<svc>.onrender.com`.
3. Deploy → you get `https://<your-app>.vercel.app`.
4. Go back to Render and set `CORS_ORIGINS` to that Vercel URL, then redeploy the backend.

## Step 5 — Verify
- Open the Vercel URL → it lands directly on the dashboard (no login).
- Upload a document → it embeds via Jina and indexes into Qdrant.
- Ask the agents / assistant → answers stream from Groq (fast, cloud).

---

## Notes & gotchas
- **Render free** spins down after ~15 min idle; the first request then cold-starts
  (~30–60 s). Fine for a demo; upgrade the plan to keep it warm.
- **Ephemeral disk**: document metadata (Postgres) and vectors (Qdrant) persist;
  only raw uploaded file bytes + workflow checkpoints reset on restart. Search
  keeps working; re-processing an old file after a restart won't.
- **Neon SSL**: if the DB won't connect, confirm the URL ends with `?ssl=require`.
- **Embedding dimension**: `EMBEDDING_DIM=768` must match the Qdrant collection.
  Changing the embedding model means using a fresh collection name.
- **RAM**: if the backend OOMs on Render free (512 MB), deploy the same Docker
  image to a **Hugging Face Space** (Docker SDK, 16 GB free) instead — set the
  same env vars there.

## Running locally (unchanged)
```bash
docker compose up -d --build     # Ollama + Chroma + SQLite, all local
```
Local uses the default providers; the cloud values only apply where you set them.
