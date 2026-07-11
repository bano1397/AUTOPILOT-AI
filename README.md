# AutoPilot AI

> **Enterprise Multi-Agent Business Automation Platform** — an AI employee that reads
> emails, understands documents, researches the web, plans tasks, retrieves company
> knowledge, and executes business workflows autonomously using LangChain & LangGraph.

Built as a production-grade, extensible platform: pluggable providers, plugin
auto-discovery, an event bus, conversation memory, full RAG, checkpointed
human-in-the-loop workflows, and end-to-end AI observability. (An MCP layer is
designed but not yet built — see the guides.) Full design in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md); as-built detail in
[`docs/PROJECT_ANALYSIS.md`](docs/PROJECT_ANALYSIS.md).

## Features

- **Authentication & RBAC** — JWT with rotating, revocable refresh tokens
  (httpOnly cookie), admin/user roles, rate-limited auth, security headers.
- **Document intelligence** — upload → OCR-ready extraction → chunk → embed →
  ChromaDB index, with per-document status.
- **RAG** — cited semantic search and retrieval-grounded answers (honest
  "no sources" instead of hallucinating).
- **Multi-agent system** — a LangGraph supervisor routes to knowledge, general,
  research (live web), and planner agents; conversation memory; every LLM call
  audited.
- **Workflows & HITL** — persistent runs with step timelines, and approvals
  that pause a run and resume it from a checkpoint across requests.
- **Automation** — event-driven notifications (in-app/Telegram/SMTP), a
  scheduled daily digest, task management.
- **Observability** — an analytics dashboard over the AI execution audit trail
  (tokens, cost, latency, error rate).

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI · SQLAlchemy 2.0 (async) · Alembic · Pydantic v2 |
| AI | LangChain · LangGraph · Ollama (abstracted) · ChromaDB |
| Frontend | Next.js 14 (App Router) · TypeScript · Tailwind · shadcn/ui · TanStack Query · Zustand |
| Database | SQLite (dev) → PostgreSQL-ready |
| Infra | Docker · Docker Compose |

## Repository layout

```
autopilot-ai/
├── backend/            # FastAPI app (features/, agents/, platform/, infrastructure/, rag/)
├── frontend/           # Next.js app (src/app, components, features, lib)
├── docs/               # ARCHITECTURE.md + guides + diagrams
├── docker-compose.yml  # backend · frontend · ollama · chromadb
└── .github/workflows/  # CI
```

---

## Quickstart

### Option A — Docker (one command)

```bash
cp .env.example .env      # set JWT_SECRET_KEY for anything non-local
docker compose up --build
```

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs

Pull local models (used from M3 onward):

```bash
docker compose exec ollama ollama pull llama3
docker compose exec ollama ollama pull nomic-embed-text
```

### Option B — Local development

**Backend** (Python 3.11+):

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Unix: source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example ../.env
alembic upgrade head
uvicorn app.main:app --reload                       # http://localhost:8000
```

**Frontend** (Node 20+):

```bash
cd frontend
npm install
cp .env.example .env.local                          # NEXT_PUBLIC_API_URL
npm run dev                                          # http://localhost:3000
```

---

## Configuration

All configuration is environment-driven. See [`.env.example`](.env.example)
(backend) and [`frontend/.env.example`](frontend/.env.example). Never commit a
real `.env`.

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | Async SQLAlchemy URL | `sqlite+aiosqlite:///./autopilot.db` |
| `JWT_SECRET_KEY` | JWT signing secret (**set in production**) | dev placeholder |
| `CORS_ORIGINS` | Allowed browser origins (comma-separated) | `http://localhost:3000` |
| `NEXT_PUBLIC_API_URL` | Backend base URL (frontend) | `http://localhost:8000` |

Generate a strong secret: `python -c "import secrets; print(secrets.token_urlsafe(64))"`

---

## Quality gates

```bash
# backend
cd backend && ruff check . && mypy app && pytest

# frontend
cd frontend && npm run lint && npm run type-check && npm run build
```

CI runs all of the above on every push and pull request.

---

## Status

**All milestones (M1–M5) complete — the platform is feature-complete.**
Foundation · Documents & RAG · Agents & LLM · Workflows & Automation ·
Hardening & Ship. Everything in the Features list above works end-to-end
(verified live against Ollama + ChromaDB). As-built detail:
[`docs/PROJECT_ANALYSIS.md`](docs/PROJECT_ANALYSIS.md); design:
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

> Chat/agent features use the Ollama model set by `LLM_MODEL` (default
> `llama3`; `llama3.2` is a lighter alternative):
> `docker compose exec ollama ollama pull llama3`

## Documentation

- [Architecture blueprint](docs/ARCHITECTURE.md) · [As-built analysis](docs/PROJECT_ANALYSIS.md)
- Guides: [API](docs/guides/api-guide.md) · [Development](docs/guides/development-guide.md) ·
  [Deployment](docs/guides/deployment-guide.md) · [Testing](docs/guides/testing-guide.md) ·
  [Agent development](docs/guides/agent-development-guide.md) ·
  [Plugin development](docs/guides/plugin-development-guide.md) ·
  [MCP integration (planned)](docs/guides/mcp-integration-guide.md)

## License

MIT

