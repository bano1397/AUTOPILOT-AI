# AutoPilot AI — Project Analysis (As-Built, all milestones complete)

> **What this document is:** a factual analysis of the codebase *as it exists today* —
> every module, layer, decision, and verification. The companion
> [`ARCHITECTURE.md`](ARCHITECTURE.md) is the forward-looking blueprint (the "should be");
> this file is the "is". Updated at milestone boundaries.
>
> **Last updated:** 2026-07-11 · **Status:** M1–M5 complete — project feature-complete

---

## 1. Executive summary

AutoPilot AI is an enterprise multi-agent business automation platform. M1 delivered the
production-grade foundation; M2 delivered the complete document-intelligence / RAG
vertical on top of it:

- **Backend (M1)** — FastAPI app spine with structured JSON logging, correlation IDs,
  middleware, health/readiness probes; platform engines (event bus, plugin registry +
  auto-discovery scanner); async SQLAlchemy 2.0 + Alembic migrations; complete
  authentication (argon2id + JWT with rotating, revocable refresh tokens); RBAC and an
  admin users API; a standard response envelope and centralized exception handling.
- **Backend (M2)** — secure document upload (magic-byte validation, random storage
  names) behind a `StorageProvider` port; an event-driven ingestion pipeline
  (extract → chunk → embed → index) driven by the `DocumentUploaded` domain event;
  `EmbeddingProvider` (Ollama) and `VectorStoreProvider` (ChromaDB v2 REST) ports;
  an owner-isolated semantic retrieval API with citations.
- **Backend (M3)** — `LLMProvider` port with an Ollama chat implementation; **AI
  observability** (`AiExecution` audit row for every LLM call — prompt, model, tokens,
  cost, timing, error, correlation id — via a recorder no generation bypasses, plus a
  provider/model price table); **RAG-grounded answering** (`POST /rag/ask`: retrieve →
  grounded prompt → cited answer; honest LLM-skip when nothing is retrieved); a
  **LangGraph supervisor graph** routing requests to registry-registered agents
  (knowledge = RAG-grounded, general = direct LLM; fail-safe routing toward knowledge);
  and **conversation memory** (`Conversation`/`Message` tables, last-10-turn history fed
  back into agent prompts, owner-scoped conversations API).
- **Backend (M4)** — every agent execution is a **persistent workflow run** (steps,
  timing, status, input/output) driven by a generic executor over `astream`;
  **human-in-the-loop approvals** with LangGraph checkpointing (a run pauses at the
  approval gate and resumes across requests via `Command(resume=…)`,
  `thread_id = run_id`); **event-driven notifications** (in-app always; Telegram/SMTP
  config-gated) fanned out from `ApprovalRequired`/`WorkflowFailed`/`DocumentIndexed`
  with per-channel failure isolation; an **APScheduler daily digest** composing the
  notification dispatcher; a **research agent** (key-less DuckDuckGo over httpx,
  stdlib-HTML-parsing, cited web sources) and a **task planner agent** (strict-JSON
  decomposition with layered parsing, persisted prioritized tasks) — the supervisor
  now orchestrates five agents with a **deterministic fast-path** for explicit
  commands ("research …", "plan …") that skips the classifier entirely.
- **Frontend** — Next.js 14 (App Router, TypeScript strict) with Tailwind + shadcn/ui,
  dark mode, TanStack Query, a typed API client (single-flight token refresh, multipart
  + pagination-meta support), guarded dashboard shell, and the feature pages:
  **Documents** (upload, live status polling, pagination, delete), **Knowledge**
  (semantic search with citations), **Assistant** (grounded Q&A with grounded/ungrounded
  badges and collapsible sources), **Agents** (chat thread routed through the
  supervisor, per-message agent badge, require-approval toggle, web-source links,
  conversation continuity), **Tasks** (create/filter/status/delete with planner-source
  badges), **Workflows** (runs table with expandable step timelines), **Approvals**
  (pending review cards with approve/reject), and a topbar **notifications bell**
  (unread badge, dropdown, mark-read).
- **Infrastructure** — multi-stage Docker images, one-command `docker compose up`
  (backend, frontend, ollama, chromadb — fully env-wired), CI running the exact local
  quality gates.

**Scale:** 191 backend tests (+3 opt-in external), 166 backend source files (mypy
strict), ~36 HTTP endpoints, 10 Alembic migrations, 9 port interfaces (database,
event bus, storage, extraction, embedding, vector store, LLM, **search**,
**notification**) with concrete registry-registered implementations, 5 registered
agents (supervisor, knowledge, general, **research**, **planner**), and 11 frontend
routes.

**Quality bar (enforced every sub-step):** `pytest` green · `ruff check` clean ·
`mypy --strict` clean · `tsc --noEmit` clean · `eslint` clean · production `next build`
succeeds · Docker images build and run.

---

## 2. Repository layout

```
AutoPilot AI/
├── docs/
│   ├── ARCHITECTURE.md          # Approved blueprint v2.0 (design, §1–§33)
│   └── PROJECT_ANALYSIS.md      # This file (as-built)
├── backend/
│   ├── app/                     # Application package (layered, feature-first)
│   ├── alembic/                 # Migrations (2 revisions)
│   ├── tests/                   # unit/ + integration/ (47 tests)
│   ├── pyproject.toml           # Deps + ruff/mypy/pytest config
│   ├── Dockerfile               # Multi-stage, non-root
│   └── docker-entrypoint.sh     # alembic upgrade head → uvicorn
├── frontend/
│   ├── src/                     # app/ (routes), components/, features/, lib/
│   ├── Dockerfile               # Multi-stage, Next standalone output, non-root
│   └── package.json             # Scripts: dev/build/lint/type-check/format
├── docker-compose.yml           # backend + frontend + ollama + chromadb
├── .github/workflows/ci.yml     # Backend + frontend gate jobs (parallel)
└── README.md                    # Quickstart + stack overview
```

---

## 3. Backend architecture

### 3.1 Layering model

Every feature follows the same strict layering; requests flow downward only:

```
Router (thin HTTP) → Service (use-cases, owns commit) → Repository (data access)
                       ↓                                   ↓
                    Schemas (Pydantic v2 I/O)           Models (SQLAlchemy 2.0)
```

- **Routers** never touch the DB; they translate HTTP ⇄ service calls.
- **Services** are instantiated per-request from the injected `AsyncSession` and act as
  a lightweight unit-of-work: they create their repositories and own the transaction
  commit.
- **Repositories** are the only layer issuing queries.

### 3.2 `app/core/` — cross-cutting concerns

| Module | Responsibility |
|---|---|
| `config.py` | Pydantic-settings `Settings` (env-driven): app meta, `DATABASE_URL`, JWT secret/algorithm/lifetimes, CORS origins, log level |
| `logging.py` | Structured JSON logging (structlog-style processors), correlation-id bound to every log line |
| `middleware.py` | Correlation-ID middleware (accepts/generates `X-Correlation-ID`, echoes on response) + request logging |
| `schemas.py` | `ApiResponse[T]` / `ErrorResponse` / `ErrorDetail` / `PageMeta` — the standard envelope every endpoint returns |
| `exceptions.py` | `AppError` hierarchy (`ConflictError`, `AuthenticationError`, `PermissionDeniedError`, `NotFoundError`, …) each carrying `code` + `status_code` |
| `error_handlers.py` | Maps `AppError`, request-validation errors, and unhandled exceptions to the error envelope (with correlation id); registered on the app |
| `security.py` | argon2id hashing (`argon2-cffi`), JWT create/decode (PyJWT) — access tokens carry `sub`/`role`/`type`, refresh tokens carry a `jti`; sha256 token hashing for server-side storage |
| `pagination.py` | `PaginationParams` query dependency (bounds: `page≥1`, `1≤page_size≤100`) + `build_page_meta` |
| `dependencies.py` | Shared DI seams (DB session provider) |

**The envelope.** All feature endpoints return
`{"success": true, "data": …, "meta": …}` or
`{"success": false, "error": {"code", "message", "details", "correlation_id"}}`.
Only infra probes (`/health`, `/health/ready`, `/`) stay raw.

### 3.3 `app/platform/` — extensibility engines

| Engine | What it does |
|---|---|
| `events/bus.py` | Async in-process event bus: typed subscribe/publish, per-handler error isolation (one failing handler never breaks others), used as the seam for event-driven agents (blueprint §7) |
| `registry/base.py` + `registries.py` | Generic plugin `Registry` (register/get/list, duplicate detection) with concrete registries for future providers (LLM, embeddings, tools, …) — blueprint §5/§6 |
| `registry/scanner.py` | Package scanner that auto-discovers and imports plugin modules so registration is decorator-driven, no central import list |
| `rag/chunking.py` | Deterministic sliding-window `TextChunker` (settings-driven size/overlap, soft whitespace breaks, guaranteed forward progress) — reused by every future RAG source |

### 3.4 `app/domain/` — contracts

Protocol-style ports so every infrastructure choice is swappable (blueprint §5), each
with a registry-registered default implementation in `app/infrastructure/`:

| Port | Default implementation |
|---|---|
| `DatabaseProvider` | SQLAlchemy async (SQLite → Postgres by URL) |
| `EventBus` | In-process async bus (per-handler error isolation) |
| `StorageProvider` (save/get/delete/url_for) | Local filesystem — random UUID names, 2-char sharding, path-traversal guard, threaded I/O |
| `TextExtractor` | Per-MIME: pypdf, python-docx, openpyxl, UTF-8 text — parsing offloaded to worker threads |
| `EmbeddingProvider` | Ollama `/api/embed` over httpx (batched, injectable client) |
| `VectorStoreProvider` (upsert/query/delete) | ChromaDB **v2 REST over httpx** — deliberately no SDK: four endpoints, small dependency tree, wire-format unit-testable, verified against a real server |

`events.py` — the domain event catalog (13 events defined from the outset;
`DocumentUploaded`/`DocumentIndexed` are live producers/consumers today).

### 3.5 `app/database/` + `app/infrastructure/`

- `base.py` — `Base` declarative class (naming conventions for Alembic autogenerate).
- `mixins.py` — `TimestampMixin` etc.
- `engine.py` — async engine/session factory from `DATABASE_URL`
  (SQLite + `aiosqlite` in dev; PostgreSQL-ready by URL swap).
- `models/__init__.py` — the model registry imported by Alembic (imports `User`,
  `RefreshToken`).
- `infrastructure/database/sqlalchemy_provider.py` — the concrete DB provider behind the
  domain interface.

**Migrations (Alembic, async template):**

| Revision | Content |
|---|---|
| `09ae726a6f3c` | Initial `users` table |
| `05de535d6e4a` | `refresh_tokens` table (jti, sha256 token hash, expiry, revoked flag, FK → users) |
| `ba0a175b933a` | `documents` table (status lifecycle, storage path, JSON metadata, FK → users) |
| `929fb5c946c5` | `document_chunks` table (chunk_index unique per doc, vector_id, preview, FK → documents) |

### 3.6 Features

#### `features/system` — probes
`GET /health` (liveness), `GET /health/ready` (checks DB connectivity), `GET /` (app info).

#### `features/auth` — authentication (blueprint §8)
Endpoints (all enveloped, mounted at `/api/v1/auth`):

| Endpoint | Behavior |
|---|---|
| `POST /register` | 201; duplicate email → 409 `CONFLICT`; weak password → 422 validation envelope |
| `POST /login` | Verifies argon2 hash → access + refresh token pair; wrong credentials → 401 |
| `POST /refresh` | **Rotation with revocation**: presented refresh token validated → its DB record revoked → new pair issued. Replay of the old token → 401 |
| `POST /logout` | Revokes the presented refresh token server-side |
| `GET /me` | Returns the authenticated user; requires bearer token |

Security design: argon2id hashing; short-lived access tokens; refresh tokens are
*stateful* (persisted as `jti` + sha256 hash + expiry + revoked flag) so a stolen or
already-rotated token is dead on arrival. `get_current_user` uses `HTTPBearer` with
`auto_error=False` so auth failures return the standard 401 envelope, not FastAPI's
default.

#### `features/documents` — document intelligence (M2, blueprint §17/§23.2)

Endpoints (enveloped, authenticated, owner-scoped, at `/api/v1/documents`):

| Endpoint | Behavior |
|---|---|
| `POST ""` | Multipart upload → 201. Validation: extension allowlist (pdf/docx/xlsx/txt/csv), declared-MIME check, **magic bytes decisive** (`%PDF-`, zip `PK`, strict UTF-8), size cap (`MAX_UPLOAD_SIZE_MB`, default 25) → 413/415/422. Stored under a random UUID name via `StorageProvider`; canonical MIME persisted (never the client's claim) |
| `GET ""` | Paginated, owner-scoped list |
| `GET /{id}` | Detail; another user's document is a 404 (no existence leak) |
| `DELETE /{id}` | DB rows (document + chunks) deleted and committed first; file + vectors removed best-effort after (DB is the source of truth) |

**Ingestion pipeline** (`ingestion.py`) — event-driven: upload commits, publishes
`DocumentUploaded`, and the subscriber (wired in `main.py`, resolving providers from
`app.state` at event time) runs `extract → chunk → persist chunks → embed → upsert
vectors → fill vector_id`, advancing `UPLOADED → PROCESSING → INDEXED | FAILED` with an
idempotency guard and the failure reason recorded in document metadata. Chunk row UUIDs
double as vector ids, so the relational and vector stores share one key. The in-process
bus delivers synchronously inside `publish` (deterministic; the task-queue scale path
changes the bus, not this service).

Models: `Document` (status lifecycle, storage path, JSON metadata) and `DocumentChunk`
(chunk_index unique per document, 500-char preview — ChromaDB holds full text —
`vector_id`, JSON metadata).

#### `features/rag` — semantic retrieval (M2)

`POST /api/v1/rag/query` (`query` 1–2000 chars, `top_k` 1–20): embeds the query,
similarity-searches with a hard `where user_id` filter (owner isolation at the vector
store), returns cited matches — `document_id`, `filename`, `chunk_index`, full chunk
`text`, `distance` — straight from vector metadata (no DB round-trip). Provider outages
surface as 502 `UPSTREAM_SERVICE_ERROR` naming the failing provider.

#### `features/users` — user management + RBAC (blueprint §9)
- `require_role(*roles)` dependency factory (built on `get_current_user`) raising
  `PermissionDeniedError` → 403 envelope; `require_admin` is the canonical instance.
- `GET /api/v1/users` — admin-only, paginated (`ApiResponse[list[UserRead]]` with
  populated `PageMeta`).
- `GET /api/v1/users/{id}` — admin-only; missing → 404 `NOT_FOUND`.
- Ownership: the users feature is the canonical home of `User`-related repository and
  read schema; auth imports from here (refactored in sub-step 5 for DRY).

### 3.7 App assembly (`main.py`)

Lifespan-managed startup/shutdown → logging configured → middleware stack →
exception handlers registered → CORS (origins from settings) → system router (raw) +
`/api/v1` router (auth, users).

---

### M3 additions (Agents & LLM)

| Module | Role |
|---|---|
| `domain/interfaces/llm.py` | `LLMProvider` port: `chat(messages, temperature, max_tokens) → LLMResult` (content **+ token counts + timing** — observability is in the contract); `ChatMessage`/`ChatRole`; `history_to_messages` helper |
| `infrastructure/llm/ollama.py` | Ollama `/api/chat` over plain httpx (same thin-provider pattern as M2), ns→ms timing mapping, 300 s timeout for CPU generation, registered `kind="llm"` |
| `platform/observability/` | `AiExecution` model (user SET NULL — audit outlives accounts; feature/agent/provider/model/prompt JSON/preview/tokens/cost/duration/error/correlation id), `(provider, model)` price table (`compute_cost`, local = $0), and `AiExecutionRecorder` — the choke-point every LLM call goes through: failures are recorded then re-raised; recording failures never break the feature; publishes `CostRecorded` |
| `features/rag/` (extended) | `POST /rag/ask`: retrieve → grounded prompt (`prompts.py`, "answer ONLY from numbered context, cite [n]") → recorded LLM call → answer + sources; **no retrieval ⇒ LLM skipped** (honest, hallucination-free, free); LLM outage → 502 with the failed call still audited |
| `agents/` | `BaseAgent` contract (pure `state → partial state` nodes, constructor-injected deps); `SupervisorAgent` (one-word classification, temp 0, **fail-safe parse toward knowledge**), `KnowledgeAgent` (delegates `RagAskService`), `GeneralAgent` (direct LLM) — all `@register_agent`; per-agent `prompts.py` |
| `workflows/` | JSON-friendly `AgentState` (TypedDict, partial updates); `build_agent_graph`: supervisor → conditional route → agent → END, generic over the agents map |
| `features/agents/` | `GET /agents` (registry introspection), `POST /agents/ask` (resolve conversation → history → run graph → persist exchange → respond with `conversation_id`) |
| `features/conversations/` | `Conversation` + `Message` (integer `position` for stable ordering — SQLite timestamps are second-granular; `meta` JSON keeps agent/model/grounded/sources for re-rendering); last-10-turn history into prompts; owner-scoped list/detail API (foreign access → 404, no existence leak) |

Memory-model status vs. blueprint: **working memory** = graph state ✓ · **knowledge
memory** = RAG ✓ · **conversation memory** = this milestone ✓ · preference/long-term/
workflow-checkpoint levels are M4+ items.

---

### M4 additions (Workflows & Automation)

| Module | Role |
|---|---|
| `features/workflows/` | `WorkflowRun`/`WorkflowStep` models; `WorkflowExecutor` drives any graph via `astream(stream_mode="updates")` recording each node with timing (short-lived sessions — the AI recorder writes mid-run), publishes the workflow event catalog, detects `__interrupt__`, and `resume()` continues from the checkpoint with continued step positions and accumulated duration; owner-scoped runs API |
| `workflows/checkpointer.py`, `workflows/nodes.py` | `AsyncSqliteSaver` lifecycle wrapper (lifespan-managed, `thread_id = run_id`); the generic `approval_gate` node — pass-through unless `needs_approval`, else `interrupt(draft)`; rejection replaces the answer and drops sources |
| `features/approvals/` | `Approval` model (draft + conversation context in payload); decide = **resume first, then mark decided** (failed resume stays pending/retryable); records the exchange with `decision` meta; `ApprovalRequired`/`ApprovalReceived` events; double-decision → 409, foreign → 404 |
| `features/notifications/` + `infrastructure/notifications/` | `NotificationProvider` port; in-app (DB, always on), Telegram (httpx, config-gated), SMTP (stdlib in a thread, config-gated); dispatcher with per-channel failure isolation; subscribers turn `ApprovalRequired`/`WorkflowFailed`/`DocumentIndexed` into notifications (handlers resolve owners from the DB); list/unread-count/mark-read API |
| `features/scheduler/` | `SchedulerManager` over `AsyncIOScheduler` (UTC tzinfo — the string `'UTC'` is silently ignored); code-defined jobs, deterministic admin "run now"; daily digest composes the dispatcher (quiet users skipped) |
| `infrastructure/search/` + `agents/research/` | `SearchProvider` port; key-less DuckDuckGo (stdlib `html.parser`, redirect decoding, scheme guard); research agent: fetch top 3 (failed fetch → snippet fallback), cited synthesis, `web_sources` response field (deliberately not the RAG citation shape) |
| `features/tasks/` + `agents/planner/` | Task CRUD (priority/status enums, `source` manual/planner); planner agent: strict-JSON prompt, layered parsing (fence-strip → bracket-substring, per-item validation), honest unparseable path (nothing persisted) |
| Supervisor | Five-agent routing with **deterministic fast-path** for explicit commands — added after a live llama3.2 mis-route; skips the classifier LLM call entirely |

---

## 4. Frontend architecture

### 4.1 Stack & structure

Next.js 14.2 (App Router) · React 18 · TypeScript strict · Tailwind 3.4 +
shadcn/ui-style primitives (hand-authored) · TanStack Query · Zustand · React Hook Form
+ Zod (v4) · next-themes (dark mode) · Prettier + ESLint.

```
src/
├── app/
│   ├── (auth)/        # login, register — redirects to /dashboard if already authed
│   ├── (dashboard)/   # AuthGuard-protected shell: dashboard, documents, knowledge
│   ├── layout.tsx     # Root layout (theme + query providers)
│   └── page.tsx       # Landing
├── components/
│   ├── ui/            # button, input, label, card, badge, table (shadcn-style)
│   ├── auth/          # auth-guard.tsx (client-side route guard)
│   ├── documents/     # status-badge, document-upload, documents-table
│   ├── layout/        # sidebar, topbar, nav-items (future items disabled, no 404s)
│   └── common/        # theme-toggle (hydration-safe)
├── features/
│   ├── auth/          # types, zod schemas, api, TanStack Query hooks
│   ├── documents/     # types, client-side upload validation, api, hooks
│   └── rag/           # types, api, useRagQuery hook
└── lib/
    ├── api/           # types.ts + client.ts (typed fetch wrapper: envelope unwrap,
    │                  #   single-flight 401 refresh, FormData, pagination meta)
    ├── auth/store.ts  # Zustand + persist (localStorage), useAuthHydrated
    ├── config.ts      # NEXT_PUBLIC_API_URL
    └── utils.ts       # cn(), formatBytes(), formatDate()
```

### 4.2 Key mechanisms

- **API client** (`lib/api/client.ts`): attaches bearer token, unwraps the
  `{success,data}` envelope, throws typed `ApiError` on failure, and on 401 performs a
  **single-flight refresh** (concurrent 401s share one refresh promise) then retries the
  original request once. Reads tokens via `useAuthStore.getState()` — store never
  imports the client, so no dependency cycle.
- **Auth store**: access/refresh tokens + user persisted to localStorage;
  `useAuthHydrated` gates guards on rehydration so protected pages don't flash or
  redirect before storage loads. (Hardening path — refresh token in an httpOnly cookie —
  is documented for M5.)
- **Guards**: client-side (`AuthGuard` for `(dashboard)`, inverse redirect in
  `(auth)`), because tokens live in localStorage and are invisible to server middleware.
- **Separation rule**: UI (pages/components) ⊥ validation (zod schemas) ⊥ data-fetching
  (query hooks) — each in its own module.
- **Documents page (M2)**: upload with instant client-side validation (mirrors backend
  rules; server enforces), status badges, chunk counts, failure reasons in-row,
  two-step inline delete confirm, Prev/Next pagination. `useDocuments` polls every 2s
  **only while** a visible document is still ingesting — self-stopping live status.
- **Knowledge page (M2)**: on-demand semantic search (mutation, nothing fires on
  mount) rendering citation cards: filename, chunk number, distance, matched text.

---

### M3 additions (frontend)

- `features/rag` slice extended with `ragAsk`/`useRagAsk`; new `features/agents` slice
  (`agentAsk` with `conversation_id` continuity, `useAgentAsk`).
- **Assistant page** (`/assistant`): grounded Q&A — success "Grounded" badge + model tag
  vs. warning "No sources found" (mirrors the backend's no-hallucination path);
  collapsible numbered sources.
- **Agents page** (`/agents`): chat thread through the supervisor graph — user/assistant
  bubbles, per-message agent + grounded badges, shared `SourcesList` component
  (extracted, used by both pages), auto-scroll, conversation id kept across turns.

---

## 5. Infrastructure

### 5.1 Docker

| Image | Design |
|---|---|
| `backend/Dockerfile` | Multi-stage (`python:3.12-slim` builder → slim runtime), non-root user, entrypoint runs `alembic upgrade head` before `uvicorn` so the schema is always current on boot |
| `frontend/Dockerfile` | Multi-stage using Next **standalone** output (small runtime), non-root; `NEXT_PUBLIC_API_URL` is a build arg (baked at build time; browser reaches the backend via the host) |

### 5.2 Compose (`docker-compose.yml`)

Services: **backend** (port 8000, SQLite on a named volume at `/data`), **frontend**
(port 3000), **ollama** (model volume), **chromadb** (vector volume) — with
healthchecks and env wiring. Ollama/ChromaDB are provisioned now so M2+ (RAG, agents)
lands on a running substrate. Postgres is the documented scale path (URL swap).

### 5.3 CI (`.github/workflows/ci.yml`)

Two parallel jobs mirroring the local gates: **backend** (ruff → mypy strict → pytest)
and **frontend** (eslint → tsc → production build).

---

## 6. Test coverage (191 tests + 3 opt-in external)

| Suite | Covers |
|---|---|
| `unit/test_security.py` | argon2 hash/verify incl. malformed-hash handling; JWT round-trip; expiry rejection |
| `unit/test_event_bus.py` | subscribe/publish, handler error isolation |
| `unit/test_registry.py`, `test_scanner.py` | plugin registration, duplicate detection, auto-discovery |
| `unit/test_health.py`, `test_app_wiring.py` | probes, middleware/correlation-id, app assembly |
| `integration/test_database.py`, `test_readiness.py` | engine/session, readiness ↔ DB |
| `integration/test_auth.py` | register (201/409/422), login (200/401), `/me` auth-gating, **refresh rotation invalidates old token (replay → 401)**, logout revocation |
| `integration/test_users.py` | 401 unauthenticated → 403 non-admin → 200 admin; pagination math (page_size=2 over 5 users → total=5, pages=3); 404 |
| `unit/test_document_validation.py` | upload validation matrix: magic bytes, MIME mismatch, path-component stripping, size/empty/extension rejections |
| `unit/test_chunking.py`, `test_extractors.py` | chunker properties (overlap, soft breaks, progress); real DOCX/XLSX/PDF bytes built in-test (incl. a programmatically assembled valid PDF) |
| `unit/test_ollama_embeddings.py`, `test_chroma_vectorstore.py` | exact wire formats via `httpx.MockTransport` (batching 32/32/6, get-or-create caching, query parsing, error propagation) |
| `integration/test_documents.py` | upload flows (201/413/415/422), owner scoping, random storage names, delete removes file |
| `integration/test_ingestion.py` | upload → `indexed` with chunk rows; vector upsert keyed by chunk id with correct metadata; embedding outage → `failed` + rollback (no chunks, no vectors); delete removes chunks + vectors |
| `integration/test_rag.py` | cited matches, owner isolation, empty index, validation bounds, provider outage → 502 |
| `unit/test_ollama_llm.py` | chat wire format, generation options, usage/timing mapping, error handling (MockTransport) |
| `unit/test_pricing.py` | cost table math (unpriced → $0, priced → exact, zero-token → $0) |
| `integration/test_observability.py` | recorder: success row fields, failure row + re-raise, `CostRecorded` event with matching id, correlation-id capture, broken store never breaks the call |
| `integration/test_rag_ask.py` | grounded answer + sources + **prompt-content assertions**, audit row per ask, no-context skips the LLM, outage → 502 with the failure audited, bounds |
| `integration/test_agents.py` | routing to knowledge (sources, exactly 2 LLM calls) / general; garbage classification falls back to knowledge (1 call, honest empty); full audit trail (supervisor + worker rows); registry listing; auth; bounds |
| `integration/test_conversations.py` | thread creation + persisted exchange with meta; follow-up reuses thread and **prior turns appear in the LLM prompt**; positions 0–3; owner scoping (foreign read/continue → 404); unknown id → 404; auth |
| `integration/test_workflows.py` | completed run with steps/positions/timing/input/output summary; failed run recorded + error propagates; owner scoping; auth |
| `integration/test_approvals.py` | pause leaves run `awaiting_approval` + conversation empty + draft in pending list; **approve resumes across requests** (steps `[supervisor, general, approval_gate]`); reject discards draft; double-decision 409; foreign 404 |
| `unit/test_notification_providers.py`, `integration/test_notifications.py` | Telegram wire format; dispatcher channel isolation + unknown-user skip; config-gated assembly; indexed/approval/failure events → in-app rows; unread/mark-read flow; owner scoping |
| `integration/test_scheduler.py` | admin gating (401/403); digest run-now sends exact counts to active users, skips quiet ones; pause/resume; unknown 404 |
| `unit/test_duckduckgo.py`, `integration/test_research.py` | DDG parsing/redirect-decode/scheme-guard; research routes + synthesis prompt carries fetched page & snippet fallback; fast-path skips classifier; no-results honesty; outage → 502 + run failed |
| `unit/test_plan_parsing.py`, `unit/test_supervisor_routing.py`, `integration/{test_tasks,test_planner}.py` | plan parsing matrix (fenced/prose/invalid-skip/cap); route parse precedence + fast-path boundaries; task CRUD/filter/owner; planner persists prioritized tasks, unparseable saves nothing |
| `integration/test_external_providers.py` | **opt-in** (`AUTOPILOT_EXTERNAL_TESTS=1`) round-trips against real Ollama/ChromaDB (embeddings, vector store, chat) |

Integration tests run against the real ASGI app with an isolated per-test database,
tmp-dir file storage, and in-memory fake embedding/vector providers (`tests/fakes.py`).

---

## 7. Notable decisions & trade-offs (as-built)

1. **SQLite now, Postgres later** — dev velocity; all data access is async SQLAlchemy
   behind a URL, so the swap is config-only. Compose keeps SQLite on a volume.
2. **Stateful refresh tokens** — deliberate trade of one DB lookup per refresh for real
   revocation and replay-defeat (pure-stateless JWT refresh can't be revoked).
3. **Hand-authored shadcn foundation** — instead of the interactive CLI, for
   deterministic, reviewable scaffolding.
4. **httpOnly refresh cookie (hardened in M5)** — the refresh token now lives only in
   an httpOnly cookie scoped to `/api/v1/auth` (`SameSite=Lax`, `Secure` in prod); the
   frontend persists just the short-lived access token + profile. The API still accepts
   a body token (explicit body **beats** the ambient cookie, so replayed old tokens
   can't silently succeed via the cookie) for non-browser clients. Route guards remain
   client-side by design. Remaining npm-audit advisories (5: DoS-class issues in the
   Next 14 line + transitive dev-tool `glob`/`postcss`) are fixable only by a breaking
   Next 16 migration — accepted risk, documented follow-up.
5. **`tailwind-merge` pinned to v2** — v3 targets Tailwind v4; project uses Tailwind 3.
6. **Envelope everywhere except probes** — infra endpoints stay raw for load-balancer
   compatibility.
7. **Thin HTTP providers over SDKs (M2)** — Ollama and ChromaDB are called over plain
   httpx: the needed surface is tiny, the wire format is unit-testable with
   `MockTransport`, and the `chromadb` package's heavy dependency tree (and Python 3.14
   wheel risk) is avoided. The hand-rolled Chroma v2 client was verified against a real
   server.
8. **Synchronous-in-publish ingestion (M2)** — the in-process bus awaits handlers, so
   ingestion completes before the upload response returns: deterministic tests, no
   polling; moving to a task queue later swaps the bus, not the pipeline.
9. **DB-first deletion ordering (M2)** — rows are deleted and committed before file and
   vector cleanup (best-effort): orphaned artifacts are harmless, dangling rows are bugs.
10. **Chunk UUIDs as vector ids (M2)** — one key shared by the relational and vector
    stores; the upsert is the final I/O before commit so failures roll back cleanly.
11. **Observability before generation (M3)** — the `AiExecution` recorder shipped one
    sub-step before the first user-facing LLM feature, so no generation was ever
    unaudited; auditing `/rag/ask` and the agents cost zero feature-side code.
12. **Honest no-context answers (M3)** — empty retrieval skips the LLM entirely
    (`grounded: false`), trading a "smarter-looking" reply for zero hallucination and
    zero token cost.
13. **Fail-safe routing (M3)** — unparseable supervisor output routes to the knowledge
    agent: mis-routing to RAG yields an honest empty answer; mis-routing away from it
    risks an ungrounded one.
14. **JSON-friendly graph state (M3)** — agents receive `user_id`/history as plain data
    (services take `UUID`, not ORM objects), keeping state checkpointable for M4's
    workflow persistence.
15. **Integer message positions (M3)** — SQLite timestamps are second-granular; the two
    messages of one exchange would tie on `created_at`, so ordering uses an explicit
    per-conversation position.
16. **Resume-first approval decisions (M4)** — the graph resumes *before* the approval
    is marked decided, so a failed resume leaves it pending and retryable instead of
    stranding a decided-but-unresumed run.
17. **Short-lived executor sessions (M4)** — the AI recorder writes `ai_executions`
    mid-run; holding one transaction across LLM calls would invite SQLite lock
    contention, so the executor opens a session per write.
18. **Deterministic supervisor fast-path (M4)** — live testing showed llama3.2
    mis-routing even explicit "Research …" commands; unambiguous command verbs now
    route without the classifier — more reliable *and* one LLM call cheaper.
19. **Honest degradation everywhere (M4)** — empty search → no LLM call; failed page
    fetch → snippet fallback; unparseable plan → nothing persisted, raw text shown;
    channel failure → other channels still deliver.
20. **Code-defined scheduled jobs (M4)** — no `SCHEDULED_JOB` table until user-defined
    schedules exist; the admin "run now" executes the job coroutine directly for
    deterministic behavior.
21. **App-scoped in-memory rate limiting (M5)** — sliding window per IP on
    login/register/refresh (429 in the standard envelope); per-app-instance state keeps
    tests isolated, Redis is the multi-replica path. Security headers middleware adds
    nosniff/DENY/no-referrer/CSP (docs pages exempted — Swagger needs its assets) and
    HSTS in production only.

### Bugs caught by the gates during M1 (evidence the process works)

- argon2's `InvalidHashError` subclasses `ValueError`, not `Argon2Error` — an `except`
  clause missed it (caught by unit test).
- Default short JWT secret triggered PyJWT's insecure-key warning (fixed via settings).
- `useAuthHydrated` touched the client-only `persist` API during SSR prerender —
  production build failure (fixed: init `false`, access persist only in `useEffect`).
- Next 14 template ships no `public/` dir — Docker `COPY` failed (fixed: tracked
  `public/.gitkeep`).
- Standalone `docker run` without `DATABASE_URL` defaulted to a root-owned path,
  failing migrations as the non-root user (compose sets `/data` correctly; verified).
- `session.rollback()` expires loaded objects — the ingestion failure path must
  `refresh()` before touching attributes or async SQLAlchemy raises `MissingGreenlet`.
- SQLite doesn't enforce FK cascades without a pragma (and async ORM cascade would
  lazy-load), so chunk deletion is explicit SQL.
- pypdf rejects PDFs without a valid xref/`%%EOF` — the test fixture assembles a real
  one programmatically.

---

## 8. Milestone status & roadmap

| Milestone | Scope | Status |
|---|---|---|
| **M1 — Foundation** | App spine, platform engines, DB, auth, RBAC/users, frontend scaffold + auth UI, Docker/CI | ✅ **Complete (8/8 sub-steps)** |
| **M2 — Documents & RAG** | Secure upload + storage provider, ingestion pipeline (extract → chunk → embed → index), Ollama/ChromaDB providers, retrieval API, documents + knowledge UI | ✅ **Complete (6/6 sub-steps)** |
| **M3 — Agents & LLM** | LLM provider, AI observability, grounded answering, LangGraph supervisor + agents, conversation memory, Assistant + Agents UI | ✅ **Complete (6/6 sub-steps)** |
| **M4 — Workflows & Automation** | Workflow runs + checkpointed HITL approvals, notifications (3 channels), scheduler + daily digest, research + planner agents, 5 new UI surfaces | ✅ **Complete (8/8 sub-steps)** |
| **M5 — Hardening & Ship** | httpOnly-cookie auth + security headers + rate limiting, cost/monitoring dashboard, dashboard home + settings, mobile nav + error pages, full guide set, release E2E | ✅ **Complete (6/6 sub-steps)** |

**M5 sub-steps (all verified green):**
1. Security hardening (httpOnly refresh cookie, security-headers middleware, per-IP auth rate limiting)
2. Cost & monitoring dashboard (analytics aggregation API + `/analytics` UI)
3. Dashboard home widgets + settings page
4. UI polish + accessibility (mobile nav, not-found + error boundary, aria)
5. Documentation set (7 guides + README features/endpoints)
6. **Release E2E:** full gates green both sides; opt-in external tests pass against
   real Ollama (llama3.2) + ChromaDB; live journey verified — register → login →
   upload → grounded cited RAG answer → planner agent created 7 tasks → analytics
   reported 2 executions / 500 tokens by feature → 1 completed workflow run

**M1 sub-steps (all verified green):**
1. Backend app spine (FastAPI, logging, middleware, probes)
2. Platform engines (event bus, registry, scanner)
3. Database layer (async SQLAlchemy, Alembic, mixins)
4. Authentication (argon2 + JWT + rotation) + envelope + error handling
5. RBAC + users API + pagination
6. Frontend scaffold (Next 14, Tailwind, shadcn, providers, dark mode)
7. Auth UI + typed API client + guarded dashboard shell (live E2E verified)
8. Docker images + compose + README + CI

**M2 sub-steps (all verified green):**
1. Documents feature: StorageProvider + secure upload/list/get/delete
2. Ingestion pipeline: TextExtractor providers + chunking engine + event-driven processing
3. EmbeddingProvider (Ollama) + VectorStoreProvider (Chroma v2 REST) + indexing stage
4. RAG retrieval API with citations + owner isolation
5. Documents & Knowledge UI (upload, live status, search with citations)
6. **Live full-stack E2E with real embeddings** — two topic-distinct documents uploaded,
   both `indexed`; each semantic query retrieved the correct document; deletion removed
   content from retrieval; UI journey (login → documents table → knowledge search with
   cited results) driven in a real browser against real Ollama + ChromaDB

**M3 sub-steps (all verified green):**
1. `LLMProvider` port + Ollama chat implementation (py3.14 compat verified first)
2. AI observability: `AiExecution` + price table + recorder (audits successes *and* failures)
3. RAG-grounded answering `POST /rag/ask` (retrieve → ground → cite; honest LLM-skip)
4. Assistant UI (grounded/ungrounded badges, collapsible sources)
5. LangGraph agent foundation (supervisor routing, knowledge/general agents, registry-backed `GET /agents`)
6. Conversation memory (threads, history into prompts, owner-scoped API) + Agents chat UI

> Live-LLM note (superseded in M4): the user's Ollama already served `llama3.2`, so live
> agent E2Es ran without any download (`LLM_MODEL=llama3.2`).

**M4 sub-steps (all verified green):**
1. Workflow run persistence (executor over `astream`, steps + events, runs API)
2. HITL approvals (checkpointer, approval gate `interrupt`/resume, decisions API)
3. Workflows + Approvals UI + require-approval toggle in the agents chat
4. Notifications (port + 3 channels, event subscribers, bell UI) — *caught that
   `DocumentIndexed` had never been published; ingestion now emits it*
5. Scheduler (APScheduler manager, daily digest, admin jobs API)
6. Research agent (DuckDuckGo provider, cited web sources)
7. Task planner (tasks CRUD + planner agent + `/tasks` UI)
8. **Live full-stack E2E with real llama3.2 + DuckDuckGo:** the planner turned a goal
   into 7 persisted prioritized tasks; a live routing miss ("Research …" → knowledge)
   led to the deterministic fast-path fix, after which research returned an accurate
   synthesis citing langchain.com/DataCamp/GeeksforGeeks; the approval loop paused a
   real draft, resumed it across requests on approval, and recorded the exchange; the
   `approval_required` notification appeared; workflow runs listed with durations.

---

## 9. How to run

```bash
# Full stack, one command
docker compose up --build
# → frontend http://localhost:3000 · backend http://localhost:8000/docs
# One-time: pull the embedding model (required for document indexing)
docker compose exec ollama ollama pull nomic-embed-text
# One-time: pull the chat model (required for Assistant/Agents, ~4.7 GB)
docker compose exec ollama ollama pull llama3

# Dev mode (needs ollama + chromadb running, e.g. docker compose up -d ollama chromadb)
cd backend  && uvicorn app.main:app --reload     # API :8000
cd frontend && npm run dev                        # UI  :3000

# Quality gates
cd backend  && ruff check . && mypy app && pytest
cd frontend && npm run lint && npm run type-check && npm run build

# Opt-in tests against the real Ollama/ChromaDB services
cd backend && AUTOPILOT_EXTERNAL_TESTS=1 pytest tests/integration/test_external_providers.py
```
