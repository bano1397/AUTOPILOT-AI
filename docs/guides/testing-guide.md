# Testing Guide

## Quality gates

Every change must pass, on both sides:

```bash
# backend
cd backend
ruff check .          # lint
mypy app              # strict type-check
pytest                # 200+ tests

# frontend
cd frontend
npm run lint          # eslint
npm run type-check    # tsc --noEmit (strict)
npm run build         # production build must succeed
```

CI (`.github/workflows/ci.yml`) runs the same gates on every push and PR.

## How tests are structured

- `tests/unit/` — pure logic with no I/O: security (argon2/JWT), event bus,
  registry, chunking, extractors, provider wire formats (`httpx.MockTransport`),
  plan parsing, supervisor routing.
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
