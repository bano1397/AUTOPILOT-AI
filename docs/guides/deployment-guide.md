# Deployment Guide

## One-command stack

```bash
cp .env.example .env          # set JWT_SECRET_KEY (see below)
docker compose up --build
```

Services: `backend` (:8000), `frontend` (:3000), `ollama` (:11434),
`chromadb` (:8001). Named volumes persist the SQLite DB, checkpoints,
documents, vector store, and Ollama models. The backend entrypoint runs
`alembic upgrade head` before starting.

First run — pull the models used by RAG and the agents:

```bash
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama pull llama3
```

## Production checklist

- **`JWT_SECRET_KEY`** — set a strong random value:
  `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
- **`ENVIRONMENT=production`** — enables HSTS and the `Secure` flag on the
  refresh cookie (serve over TLS, e.g. behind nginx/Caddy).
- **`CORS_ORIGINS`** — set to your real frontend origin(s).
- **Database** — SQLite is the default. For scale, switch `DATABASE_URL` to
  `postgresql+asyncpg://…`; all data access is async and migration-driven, so
  no code changes are required.

## Scaling notes (documented, not yet wired)

- Rate limiting and the event bus are in-memory (per instance). For multiple
  replicas, move both to Redis behind their existing interfaces.
- Ingestion and agent runs execute in-process; a task queue (Celery/RQ) is the
  path for heavy concurrent load.
- Move `nomic-embed-text`/`llama3` to a GPU Ollama node or a hosted LLM via the
  `LLMProvider` port.

## Known follow-ups

The Next.js 14 line and some transitive dev tooling carry npm-audit advisories
fixable only by a breaking Next 16 upgrade — tracked as a hardening follow-up
(see `PROJECT_ANALYSIS.md`).
