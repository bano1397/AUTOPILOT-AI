# Development Guide

## Prerequisites

- Python 3.11+ (developed on 3.14)
- Node.js 20+
- Docker (for Ollama + ChromaDB, or the full stack)

## Backend setup

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # Windows;  source .venv/bin/activate on Unix
pip install -e ".[dev]"
cp ../.env.example ../.env
alembic upgrade head
uvicorn app.main:app --reload   # http://localhost:8000
```

## Frontend setup

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev                     # http://localhost:3000
```

## AI dependencies

Chat, RAG, and agents need Ollama + ChromaDB. The quickest path:

```bash
docker compose up -d ollama chromadb
docker compose exec ollama ollama pull nomic-embed-text   # embeddings
docker compose exec ollama ollama pull llama3             # chat (or llama3.2)
```

Point the backend at them via `OLLAMA_BASE_URL`, `CHROMA_URL`, and `LLM_MODEL`.

## Architecture rules

- **Clean Architecture / inward-only dependencies.** `domain/` holds
  framework-free contracts; `infrastructure/` implements them; `features/` are
  layered slices (`router → service → repository → models/schemas`).
- **Every external system is behind a provider port** (LLM, embedding, vector
  store, storage, search, notification, database) resolved via the plugin
  registry. Nothing in business logic imports a vendor SDK directly.
- **Thin routers.** Business logic lives in services; routers only parse,
  validate, and shape responses.
- **All I/O is async.**

## Project layout

```
backend/app/
  core/            config, security, logging, middleware, errors, rate limiting
  domain/          entities, interfaces (ports), events
  platform/        registry, event bus, observability, prompts
  infrastructure/  provider implementations (llm, embeddings, vectorstore, …)
  features/        auth, users, documents, rag, agents, conversations,
                   workflows, approvals, notifications, scheduler, tasks, analytics
  agents/          supervisor + knowledge/general/research/planner
  workflows/       LangGraph state, graph, checkpointer, nodes
frontend/src/
  app/             App Router routes ((auth) / (dashboard) groups)
  components/      ui (shadcn), common, layout, feature widgets
  features/        per-domain api + hooks + types
  lib/             api client, auth store, config, utils
```

See [`testing-guide.md`](testing-guide.md) for the quality gates and
[`agent-development-guide.md`](agent-development-guide.md) /
[`plugin-development-guide.md`](plugin-development-guide.md) for extending.
