# Testing Guide

## Quality gates

Every change must pass, on both sides:

```bash
# backend
cd backend
ruff check .          # lint
mypy app              # strict type-check
pytest                # 580+ tests

# frontend
cd frontend
npm run lint          # eslint
npm run type-check    # tsc --noEmit (strict)
npm run build         # production build must succeed
npm run test:e2e      # Playwright, nine core journeys
```

CI (`.github/workflows/ci.yml`) runs the same gates on every push and PR, in
three jobs: backend, frontend, and e2e.

## How tests are structured

- `tests/unit/` — pure logic with no I/O: event bus, registry, chunking,
  extractors, provider wire formats (`httpx.MockTransport`), plan parsing,
  supervisor routing, prompt rendering, the memory facade, and the stub
  providers.
- `tests/integration/` — the real ASGI app against an **isolated per-test
  SQLite database**, tmp-dir file storage, and in-memory fake providers from
  `tests/fakes.py` (LLM, embeddings, vector store, search). No network.

## Writing integration tests

Fixtures set the app's providers on `app.state` before issuing requests:

```python
app.state.db = db                     # per-test SQLite
app.state.llm = FakeLLMProvider(replies=["general", "Hi!"])
app.state.ai_recorder = AiExecutionRecorder(db=db, bus=app.state.event_bus)
```

Notes:
- `ASGITransport` does **not** run the app lifespan — set `app.state.*`
  (checkpointer, scheduler, providers) directly in the fixture.
- `FakeLLMProvider.replies` is a queue for multi-call flows (e.g. supervisor
  classification then the worker answer); `fast_route` skips the classifier for
  explicit "research …"/"plan …" commands, so those flows script one fewer reply.
- Seeding ORM rows with UUID FK columns requires real `uuid.UUID` objects.

## Opt-in live tests

`tests/integration/test_external_providers.py` round-trips against real
Ollama + ChromaDB. They are skipped unless enabled:

```bash
AUTOPILOT_EXTERNAL_TESTS=1 pytest tests/integration/test_external_providers.py
```

`tests/unit/test_ocr.py` splits the same way. The configuration gating and
degradation paths run everywhere; the tests that actually invoke Tesseract are
opt-in, because OCR needs a system binary pip cannot install:

```bash
pip install -e '.[ocr]' && AUTOPILOT_OCR_TESTS=1 pytest tests/unit/test_ocr.py
```

They pass against Tesseract 5.5.0 — including reading text back out of a
generated image and the scanned-PDF fallback. CI runs the suite without
Tesseract, so those three skip there.

`tests/integration/test_ops.py` does the same for the Redis event bus. The
degradation path (Redis unreachable → in-process behaviour) runs everywhere;
the cross-replica tests need a real server:

```bash
docker run -d -p 6379:6379 redis:7-alpine
pip install -e '.[redis]' && pytest tests/integration/test_ops.py
```

They pass against Redis 7, including delivery between two bus instances and
the origin check that stops a publisher handling its own event twice.

## End-to-end tests

`frontend/e2e/` drives a real browser against a **real backend** — one
configured with the stub LLM, stub embeddings, and the in-process vector store,
so the suite needs no model server, no ChromaDB, and no network:

```bash
cd frontend
npm run test:e2e        # Playwright starts both servers itself
npm run test:e2e:ui     # same, with the interactive runner
```

Playwright launches the backend on port 8100 and the frontend on 3100 — not the
usual 8000/3000, so a run can never touch your dev stack or its database. State
lives in `backend/.e2e-state/` and is wiped on every start.

**Scope, stated plainly:** these tests prove the *wiring* — uploads index,
knowledge search retrieves, the supervisor routes, citations render, the
planner writes tasks, approvals pause and resume a run, keyword retrieval
surfaces an exact token and labels it as such, publishing a workflow version
reroutes traffic (and rollback restores it), and run progress streams live over
the WebSocket. They prove nothing
about answer quality, because a stub has none. Model behaviour is out of scope
for CI by design; the opt-in live tests below are where real providers get
exercised.

Two details worth knowing before editing the suite:

- **`workers: 1` is correctness, not caution.** The backend is a single shared
  workspace with no authentication, so there is no tenant boundary to isolate
  parallel specs behind — two at once would see each other's documents.
  Journeys run in declaration order and journey 1 indexes the document that
  journeys 2 and 3 retrieve.
- **The web server runs the standalone build** (`node .next/standalone/server.js`
  with `.next/static` and `public` copied beside it), because `next.config.mjs`
  sets `output: "standalone"` and `next start` does *not* serve that layout — it
  400s on page chunks, so pages render but never hydrate. This mirrors the
  Dockerfile, so the suite exercises the real production serving path.

To debug against servers you started yourself, set `E2E_EXTERNAL_SERVERS=1` and
Playwright will leave them alone.
