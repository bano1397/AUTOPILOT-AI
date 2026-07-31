# AutoPilot AI

> **Multi-Agent Business Automation Platform** — an AI workspace that triages
> email, understands documents, researches the web, plans tasks, retrieves company
> knowledge, and executes business workflows using LangChain & LangGraph.

> ### ⚠ No authentication
> This is a **single shared workspace with no login**. Anyone who can reach the URL
> can read and write every document, conversation, and task in the instance, and
> there is no rate limiting. It is built this way deliberately — see
> [`docs/COMPLETION_PLAN.md`](docs/COMPLETION_PLAN.md) §3 — but it means **you must
> not put real business data in a publicly reachable deployment**.

Built as a production-grade, extensible platform: pluggable providers, plugin
auto-discovery, an event bus, conversation memory, full RAG, checkpointed
human-in-the-loop workflows, and end-to-end AI observability. (An MCP layer is
designed but not yet built — see the guides.) Full design in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md); as-built detail in
[`docs/PROJECT_ANALYSIS.md`](docs/PROJECT_ANALYSIS.md).

## Features

- **Email agent** — IMAP sync → nine-intent classification → entity extraction
  → RAG-grounded draft reply → **you** review, edit, and send over SMTP. Nothing
  is ever sent automatically.
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
  (tokens, cost, latency, error rate), with every call traced to the exact
  versioned prompt that produced it.
- **Tool marketplace** — typed, self-registering tools with declared schemas and
  dependencies, listable and invocable over HTTP.
- **MCP** — consumes tools from configured MCP servers (stdio + HTTP) into the
  same registry agents use, and exposes its own tools *as* an MCP server at
  `POST /api/v1/tools/mcp`.
- **Workspace preferences** — instance-wide defaults that actually change
  behavior (retrieval breadth, approval gating, notification delivery).
- **Memory** — all six levels behind one `MemoryManager`, including durable
  long-term facts the general agent recalls and grounds on, indexed in their
  own vector namespace so they never leak into document search.
- **Retrieval depth** — hybrid search (vector + BM25, fused with Reciprocal
  Rank Fusion) so exact tokens like part numbers are findable, an optional
  cross-encoder reranking stage, context compression to a token budget, and
  optional OCR for scanned PDFs and images.
- **Versioned workflows** — immutable graph specs that actually compile the
  agent graph, so publishing a version changes routing and activating an older
  one rolls it back. Runs pin the version that produced them, and clone forks
  a workflow from its active spec.
- **Live run status** — workflow progress streams to the browser over a
  WebSocket as each graph node completes.
- **Streaming answers** — the assistant renders token by token, with citations
  shown before the prose so you can judge grounding while it writes.
- **Calendar** — a local scheduling backend with free-slot search, and an agent
  that answers "when am I free?" from the real calendar rather than inventing
  a time.
- **Operations** — Prometheus `/metrics`, an optional Redis event bus for
  multi-replica correctness, and Postgres-backed workflow checkpoints that
  survive a restart.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI · SQLAlchemy 2.0 (async) · Alembic · Pydantic v2 |
| AI | LangChain · LangGraph · Ollama (abstracted) · ChromaDB |
| Frontend | Next.js 14 (App Router) · TypeScript · Tailwind · shadcn/ui · TanStack Query |
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
cp .env.example .env      # defaults are fine for local use
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
| `CORS_ORIGINS` | Allowed browser origins (comma-separated) | `http://localhost:3000` |
| `NEXT_PUBLIC_API_URL` | Backend base URL (frontend) | `http://localhost:8000` |
| `LLM_PROVIDER` | `ollama` (local) or `groq` (cloud) | `ollama` |
| `EMBEDDING_PROVIDER` | `ollama` or `jina` | `ollama` |
| `VECTOR_STORE_PROVIDER` | `chroma` or `qdrant` | `chroma` |
| `STORAGE_PROVIDER` | `local` disk or `s3`-compatible bucket | `local` |

Production templates with every cloud variable:
[`backend/.env.production.example`](backend/.env.production.example) and
[`frontend/.env.production.example`](frontend/.env.production.example).

---

## Quality gates

```bash
make check          # everything below, exactly as CI runs it
make install-hooks  # run it automatically on every push
```

```bash
# or individually
cd backend  && ruff check . && mypy app && pytest
cd frontend && npm run lint && npm run type-check && npm run build
cd frontend && npm run test:e2e   # Playwright, six core journeys
```

The e2e suite drives a real backend running the zero-dependency provider set
(`LLM_PROVIDER=stub`, `EMBEDDING_PROVIDER=stub`, `VECTOR_STORE_PROVIDER=memory`),
so it needs no model server and no network. That same set is the fastest way to
try the app locally — it starts instantly, and every answer is fixed and
unintelligent. See [`docs/guides/testing-guide.md`](docs/guides/testing-guide.md).

CI runs all of the above on every push and pull request. **The gate results are
in CI, not in this file** — a README claiming "all green" is a claim that rots.

---

## Status

Milestones M1–M5 delivered the platform described in the Features list above;
authentication was subsequently removed by design (§3 of the completion plan).
**What is built, what is not, and the plan for the rest live in
[`docs/COMPLETION_PLAN.md`](docs/COMPLETION_PLAN.md)** — it is kept honest
against actually-executed gate runs. As-built module detail:
[`docs/PROJECT_ANALYSIS.md`](docs/PROJECT_ANALYSIS.md); design blueprint:
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

Not built, deliberately: the drag-and-drop visual workflow builder. The graph
spec describes one fixed topology rather than arbitrary node wiring, so a
canvas editor would have nothing meaningful to edit; the workflow UI publishes
versions, activates, rolls back, and clones instead.

Built but **unverified against the real service**: the S3/R2 signing, the
IMAP/SMTP transports, the Jina reranker, and the Google Calendar adapter (which
is an explicit seam with no OAuth flow — it fails loudly rather than reporting
an empty calendar). Each is tested against mocks and labelled as such in code.

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

