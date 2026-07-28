# AutoPilot AI — Completion Plan

> **What this document is:** the execution plan to take the project from its
> *actual verified state* to complete. It supersedes the status sections of
> [`README.md`](../README.md) and [`PROJECT_ANALYSIS.md`](PROJECT_ANALYSIS.md),
> both of which are stale (they claim all gates green; they are not).
>
> **Companions:** [`ARCHITECTURE.md`](ARCHITECTURE.md) = the blueprint (the
> "should be") · [`PROJECT_ANALYSIS.md`](PROJECT_ANALYSIS.md) = as-built detail
> (the "is", as of the last milestone) · this file = the "what's left".
>
> **Verified:** 2026-07-28, against commit `1e3b9ce` on `main`.

---

## 1. Verified current state

Everything below was **executed**, not read off a doc.

| Gate | Command | Result |
|---|---|---|
| Backend lint | `ruff check .` | ✅ All checks passed |
| Backend types | `mypy app` (strict) | ✅ No issues in 174 source files |
| Backend tests | `pytest` | ❌ **29 integration tests failing** (3 external skipped) |
| Frontend types | `tsc --noEmit` | ✅ Clean |
| Frontend lint | `eslint` | ✅ No warnings or errors |
| Frontend build | `next build` | ✅ 13 routes built |

**Scale as built:** 174 backend source files · 37 HTTP endpoints · 10 Alembic
migrations · 10 port interfaces · 5 agents · 13 frontend routes.

**Feature verdict:** M1–M5 as described in `PROJECT_ANALYSIS.md` is genuinely
built. The docs are honest about *scope*; they are wrong about *state*. The
regression came from an undocumented pivot to a no-login public demo that was
never propagated to the tests or the docs.

---

## 2. Findings, ranked

### F1 — CI on `main` is red: 29 failing tests (blocker)

The app was converted to a shared-workspace public demo:
[`backend/app/features/auth/dependencies.py`](../backend/app/features/auth/dependencies.py)
now returns a get-or-created `public@autopilot.local` user instead of requiring
a bearer token. The test suite still asserts `401` and single-tenant row counts.

Failing files: `test_agents`, `test_analytics`, `test_approvals`, `test_auth`,
`test_conversations`, `test_documents`, `test_notifications`, `test_rag`,
`test_rag_ask`, `test_scheduler`, `test_tasks`, `test_users`, `test_workflows`,
and `tests/unit/test_no_auth_smoke.py`.

Three distinct failure causes:

1. **`require_authentication` tests** — assert `401`, now get `200`.
2. **Owner-scoping / count tests** — every request resolves to the *same* public
   user, so "user A cannot see user B's row" no longer holds, and counts are off
   by one because the public user joins the `users` table
   (`test_users::test_pagination` → `assert 6 == 5`).
3. **`test_no_auth_smoke`** — its own `client` fixture has no schema, so the
   get-or-create hits `OperationalError: no such table: users`. The one test
   written *for* the new mode is itself broken.

### F2 — `GET /api/v1/auth/me` returns 500 in the deployed demo (production bug)

Verified traceback:

```
File "/app/features/auth/router.py", line 131, in me
    return ApiResponse(data=UserRead.model_validate(current_user))
pydantic_core.ValidationError: 1 validation error for UserRead
email
  value is not a valid email address: The part after the @-sign is a
  special-use or reserved name that cannot be used with email.
  [input_value='public@autopilot.local']
```

`EmailStr` rejects `.local` as an IANA special-use TLD, so the public user can
never be serialized. Both `/auth/me` and admin `GET /users` 500. The frontend
masks it: [`auth-guard.tsx`](../frontend/src/components/auth/auth-guard.tsx)
catches the `getMe()` rejection and renders anyway, so the topbar and
Settings → Profile silently show no identity.

### F3 — Documentation drift

- [`DEPLOYMENT.md`](../DEPLOYMENT.md) instructs the reader to use
  `*/.env.production.example` — **neither file exists**.
- [`.env.example`](../.env.example) is missing every cloud variable the code
  actually reads: `LLM_PROVIDER`, `EMBEDDING_PROVIDER`,
  `VECTOR_STORE_PROVIDER`, `EMBEDDING_DIM`, `GROQ_API_KEY`, `GROQ_MODEL`,
  `GROQ_BASE_URL`, `JINA_API_KEY`, `JINA_MODEL`, `QDRANT_URL`,
  `QDRANT_API_KEY`.
- README and `PROJECT_ANALYSIS.md` describe a login-gated multi-tenant app and
  claim all gates green.
- README's headline claim that the platform "reads emails" is **not
  implemented** (no IMAP/email code exists anywhere).
- `docs/diagrams/` — promised by Architecture Appendix B (`.mmd` + PNG/SVG
  exports) — does not exist.

### F4 — Blueprint scope never built

Designed in `ARCHITECTURE.md`, absent from the code:

| Blueprint | Status |
|---|---|
| §8 MCP layer (`app/mcp/`) | Not built (guide correctly labels it "planned") |
| §19 Tool registry + marketplace | Not built — no `Tool` contract, no `app/tools/` |
| §18 Prompt registry / versioning / eval | Not built (prompts are module constants) |
| §16 Six-level memory | 4 of 6 — no long-term vector memory, no user preferences |
| FR Email agent (9-intent IMAP→draft→approve→SMTP) | Not built |
| FR Calendar agent | Not built |
| §20 Workflow versioning / rollback / clone | Not built (runs exist; definitions don't) |
| §17 OCR, hybrid search, reranking, compression | Not built (chunk→embed→vector only) |
| Workflow builder UI, WebSocket live status | Not built |
| Dashboard aggregate endpoint | Not built (UI composes 3 calls client-side) |

### F5 — Operational gaps

- ~~No end-to-end test suite (no Playwright/Cypress).~~ **Closed** — see §6 2.4.
- Event bus is in-process → correctness assumes a single replica. (The rate
  limiter is removed in Phase 0.2 along with the auth endpoints it protected,
  leaving the public URL unthrottled — see §3.)
- Render free tier has an ephemeral disk: uploaded file bytes and
  `workflow_checkpoints.db` are lost on restart (Postgres + Qdrant survive).
- Settings page is read-only display + theme; nothing persists server-side.
- `.env` holds real values in the working tree (correctly gitignored — but
  history should be audited for leaked keys before the repo goes public).

---

## 3. Decision: authentication does not apply (settled)

**The platform is a single shared workspace with no authentication. Permanent —
not a temporary demo shim.** Every request runs as one implicit workspace
identity; there are no accounts, no login, no roles.

Consequences, accepted deliberately:

- Login / register / refresh / logout endpoints and pages are **removed**, not
  hidden. So are refresh-token rotation, the httpOnly refresh cookie, the
  per-IP auth rate limiter, and RBAC (`require_admin`).
- Multi-tenant isolation tests are **deleted** — there is no second tenant to
  isolate from. This discards working, tested code; that is the intended
  trade for a materially simpler system.
- **The `user_id` columns and their query filters stay.** They cost nothing,
  keep the schema coherent, keep the ingestion→vector-metadata key chain
  intact, and leave the door open if accounts are ever wanted. Removing them
  would touch every feature module for no gain.
- Anyone with the URL has full access to all data in the instance. This is
  acceptable for a portfolio/demo deployment and must be stated plainly in the
  README — it is **not** suitable for real business documents.

The rest of this plan is written for this decision.

---

## 4. Phase 0 — Get `main` green, auth removed ✅ **DONE**

> **Completed** on branch `phase-0-remove-auth`. All six gates verified green:
> `ruff` clean · `mypy app` clean (165 files) · **195 passed, 3 skipped** ·
> `tsc` clean · `eslint` clean · `next build` 12 routes. Migration
> `c7a1e4b90f21` verified upgrade *and* downgrade against SQLite. `pyjwt` and
> `argon2-cffi` confirmed absent from a fresh environment. Findings §2 F1 and
> §2 F2 are closed.
>
> Deviation from plan, recorded: §0.2 said to keep argon2 "only if something
> still uses it" — nothing did, so `core/security.py` was deleted whole and both
> crypto dependencies dropped. §0.4's estimate was ~21 deleted / ~8 rewritten /
> ~5 added; actual was 2 files deleted outright, 1 replaced, ~16 transformed,
> and a new `test_open_access.py` (14 cases) — a net test count of 195, up from
> 191, because the open-access parametrization covers more endpoints than the
> per-file `require_authentication` tests it replaced.

**Goal:** every gate green, CI passing, the workspace-identity endpoint working,
and no dead authentication surface left behind. Nothing else starts until this
is done.

### 0.1 Fix the workspace-identity email (F2)

- In [`features/auth/dependencies.py`](../backend/app/features/auth/dependencies.py):
  change `PUBLIC_USER_EMAIL` to `workspace@autopilot.dev` — a real,
  non-reserved TLD. `.local` is what breaks `EmailStr`; the address is never
  mailed.
- Add an Alembic migration updating any existing row
  (`UPDATE users SET email='workspace@autopilot.dev' WHERE email='public@autopilot.local'`)
  so already-deployed Neon databases heal on boot — the entrypoint already runs
  `alembic upgrade head`.
- **Do not** relax `UserRead.email` to `str`. Validation caught a real bug here;
  keep it.

### 0.2 Remove the authentication surface (backend)

Delete, don't hide — dead auth code is worse than none:

- `features/auth/router.py`: drop `register`, `login`, `refresh`, `logout` and
  the refresh-cookie helpers. Keep a single identity endpoint — move
  `GET /me` to the users router as `GET /api/v1/users/me`, returning the
  workspace user, and retire the `/auth` prefix entirely.
- Delete `features/auth/service.py` token issuance/rotation, the `RefreshToken`
  model, and its repository. Add a migration dropping the `refresh_tokens`
  table.
- `core/security.py`: delete the JWT create/decode helpers. Keep the argon2
  helpers only if something still uses them — otherwise delete the module and
  drop `pyjwt` + `argon2-cffi` from `pyproject.toml`.
- `core/ratelimit.py` + its middleware wiring in `main.py`: the limiter existed
  solely to protect login/register/refresh. Delete it (and
  `AUTH_RATE_LIMIT_PER_MINUTE` from `.env.example`). Note in the README that
  no rate limiting remains — relevant for a public URL.
- `features/users`: remove `require_role` / `require_admin` and the admin-only
  gating on `GET /users`. The scheduler's admin-gated "run now" endpoint becomes
  ungated — call that out in the README as an intentional demo affordance.
- Rename `get_current_user` → `get_workspace_user` across the ~12 call sites so
  the name stops implying authentication. Keep the get-or-create race handling
  that already exists; it is correct.
- **Keep** every `user_id` column, filter, and the vector-metadata `user_id`
  scoping. Per §3.

### 0.3 Remove the authentication surface (frontend)

- Delete `src/app/(auth)/**` (login, register, layout) and
  `src/features/auth/{schemas,password-strength}.ts`.
- `src/features/auth/`: reduce to a single `getWorkspaceUser()` call against the
  new identity endpoint.
- `src/lib/api/client.ts`: delete `tryRefresh`, the single-flight refresh
  promise, the 401-retry branch, and the bearer-token header. This removes the
  most intricate code in the client — a genuine simplification.
- `src/lib/auth/store.ts`: reduce to a plain workspace-identity store (no
  tokens, no `persist`, no `useAuthHydrated`).
- `src/components/auth/auth-guard.tsx`: delete. The `(dashboard)` layout fetches
  the identity directly; nothing is being guarded.
- Topbar: keep the "Open demo · no sign-in required" affordance; drop any
  logout control.

### 0.4 Repair the test suite (F1)

With auth gone, the 29 failures resolve by deletion and rewrite, not by fixture
overrides:

- **Delete** the `*_require_authentication` tests (13 of them) — they assert a
  behavior the product no longer has.
- **Delete** the cross-tenant tests: `test_documents::test_list_is_owner_scoped_and_paginated`
  (rewrite as a plain pagination test), `test_get_other_users_document_returns_404`,
  `test_rag::test_query_is_owner_isolated`, `test_conversations::test_conversation_access_is_owner_scoped`,
  `test_approvals::test_foreign_approval_is_not_found`, `test_tasks::test_tasks_are_owner_scoped`,
  `test_notifications::test_notifications_are_owner_scoped`,
  `test_workflows::test_runs_list_is_owner_scoped`.
- **Rewrite** the count-sensitive tests for one workspace user:
  `test_users::test_pagination` (`assert 6 == 5` → seed-relative),
  `test_analytics::test_overview_aggregates_usage`,
  `test_scheduler::test_run_digest_sends_notifications_for_active_users`,
  `test_tasks::test_validation_and_auth` (split: keep validation, drop auth).
- **Rewrite** `test_auth.py` → `test_workspace_identity.py`: identity endpoint
  returns 200 with the workspace user; the user is provisioned exactly once;
  concurrent first-requests don't duplicate it (the `IntegrityError` path).
- **Fix and relocate** `tests/unit/test_no_auth_smoke.py` → `tests/integration/`
  with the DB fixture (its current failure is a missing schema, not a product
  bug).
- Delete `test_security.py`'s JWT cases; keep argon2 cases only if the module
  survives 0.2.

Expected net: ~21 tests deleted, ~8 rewritten, ~5 added.

### 0.5 Prevent recurrence

- Add a `pre-push` hook (or `make check`) running the exact CI gates:
  `ruff check . && mypy app && pytest` and
  `npm run lint && npm run type-check && npm run build`.
- Stop asserting "all gates green" in prose docs (see 1.2) — let CI be the
  single source of truth for state.

**Exit criteria:** all six gates green locally and in GitHub Actions; the
identity endpoint returns 200 on the deployed instance; `grep -ri "jwt\|bearer\|refresh_token\|login"`
over `backend/app` and `frontend/src` returns nothing but comments.

---

## 5. Phase 1 — Ship-quality demo ✅ **DONE** (1.4 blocked)

> **Completed** except the live cloud walkthrough. Gates after Phase 1+2 work:
> `ruff` clean · `mypy app` clean (191 files) · **241 passed, 5 skipped** ·
> `tsc` clean · `eslint` clean · `next build` 13 routes. Migration chain verified
> upgrade → head and downgrade → base.
>
> - **1.1** ✅ `backend/.env.production.example` and
>   `frontend/.env.production.example` created; root `.env.example` extended with
>   all 11 previously-undocumented cloud variables plus the storage block.
> - **1.2** ✅ README leads with the no-authentication warning, drops the RBAC
>   bullet and the false "reads emails" claim, lists what is *not* built, and
>   stops asserting its own gate status. `DEPLOYMENT.md` gained the R2 step and an
>   honest checkpoint-durability caveat. `PROJECT_ANALYSIS.md` §3.6 auth/users
>   marked historical; `ARCHITECTURE.md` §12 marked **descoped by decision**.
> - **1.3** ✅ `S3StorageProvider` — thin httpx client with hand-rolled SigV4
>   (no boto3, matching decision 7), registered as `storage/s3`, selected by
>   `STORAGE_PROVIDER=s3`; 14 unit tests over wire format and signing.
>   `render.yaml` now sets it and declares the four S3 secrets.
> - **1.4** ❌ **BLOCKED — needs credentials I don't have.** The live
>   Groq + Jina + Qdrant + Neon + R2 walkthrough cannot be run from here. The S3
>   signing path in particular is *unverified against a real endpoint*: unit tests
>   pin structure and determinism, they cannot prove a server accepts the
>   signature. Run `AUTOPILOT_S3_TESTS=1 … pytest
>   tests/integration/test_s3_roundtrip.py` (2 opt-in tests, written and skipped)
>   as the first thing you do with real keys.

## 5b. Phase 1 — original task list

### 1.1 Environment templates (F3)

- Create `backend/.env.production.example` and
  `frontend/.env.production.example` (referenced by `DEPLOYMENT.md` but missing).
- Extend `.env.example` with all 11 missing cloud variables, each with a comment
  on which provider it selects.

### 1.2 Honest documentation (F3)

- README: **lead with the open-access warning** — no authentication, anyone with
  the URL sees all data, no rate limiting, don't upload real business documents.
  Then replace "All milestones complete — feature-complete" with a linked, dated
  status, and remove "reads emails" from the headline until Phase 3 lands it.
  Delete the Authentication & RBAC bullet from the feature list.
- `PROJECT_ANALYSIS.md`: mark §3.6 `features/auth` and the RBAC parts of §3.6
  `features/users` as removed, note the decision (§3 of this plan), and point
  here.
- `ARCHITECTURE.md`: mark §12 (Auth & Authorization Flow) and the Auth & Users
  row of §1 as **descoped by decision**, with a one-line rationale — same
  convention the MCP guide already uses. Leave the design text in place; it
  documents a path not taken, which is worth keeping.
- `DEPLOYMENT.md`: add the Hugging Face Space path (the YAML header already sits
  in `backend/README.md`) and the ephemeral-disk caveat.

### 1.3 Durable uploads (F5)

Behind the existing `StorageProvider` port, add an S3-compatible adapter
(Cloudflare R2 free tier) and select it by env, so Render restarts stop losing
document bytes. No feature code changes — this is exactly what the port is for.

### 1.4 Verify the cloud path end-to-end

With Groq + Jina + Qdrant + Neon configured, walk: upload → indexed → cited RAG
answer → planner creates tasks → approval pauses and resumes → analytics
populates. Record the result in this file.

**Exit criteria:** a stranger can follow `DEPLOYMENT.md` start-to-finish and get
a working deployment; uploads survive a restart.

---

## 6. Phase 2 — Close the platform gaps

> **2.1 ✅ · 2.2 ✅ · 2.3 partially ✅ · 2.4 ❌ not started.**
>
> - **2.1 Tool registry + marketplace** ✅ `domain/interfaces/tool.py`
>   (`Tool` protocol + `ToolMeta`), three native tools (`vector_search`,
>   `web_search`, `create_task`) auto-discovered by the existing scanner,
>   `GET /tools`, `GET /tools/categories`, `POST /tools/{name}/invoke` with
>   per-tool pydantic input validation, and a `/tools` marketplace page with a
>   working schema-driven Run panel. 8 integration tests. `ToolMeta.permissions`
>   is metadata only, as decided — no always-passing checker was built.
> - **2.2 Prompt registry + versioning** ✅ `platform/prompts/` with immutable
>   versioned `PromptTemplate`s (Jinja2, `StrictUndefined`), a registry enforcing
>   one active version per key, and a catalog holding all five live prompts.
>   **The five bodies were verified byte-identical to the originals via AST
>   comparison against `HEAD`**, so no prompt behavior changed. `AiExecution`
>   gained `prompt_key`/`prompt_version` (migration `d3f8b25c9a17`), populated at
>   all five LLM call sites → any past generation traces to exact prompt text.
>   `GET /prompts`, `GET /prompts/{key}`, `POST /prompts/{key}/render`.
>   17 tests. **Reduced scope, deliberately:** no DB-backed authoring UI and no
>   scored evaluation / version promotion — prompts stay code-defined so there is
>   one reviewable source of truth. Those remain open (see §7.6).
> - **2.3 Memory + preferences** — **both ✅** (memory completed 2026-07-29).
>   `MemoryManager` lives in `platform/memory/` (not the blueprint's
>   `app/memory/`, to sit with the other cross-cutting platform concerns) and
>   fronts all six levels: working memory is implemented inline, the other five
>   delegate to their owning service. Levels are optional and an unconfigured
>   level raises rather than silently returning nothing.
>   Long-term memory is `memory_entries` (migration `a4d90c17e6b2`) plus a
>   **separate vector collection** (`MEMORY_COLLECTION`), with
>   `GET`/`POST`/`DELETE /memory` and `POST /memory/recall`.
>   **It changes behavior:** the general agent recalls up to 3 durable facts and
>   grounds on them, via a new `agent.general.system` **v2** — v1 is retained
>   inactive, and a test pins that v2 with no memories renders byte-identical to
>   v1, so conversations without stored facts are unchanged.
>   32 tests. Deliberate choices, each test-pinned: a separate collection rather
>   than a `kind` filter (pre-existing document vectors carry no such field, so a
>   filter would have silently dropped them from RAG); `remember` keeps the row
>   when embedding fails and reports `indexed: false` rather than lying;
>   `recall` raises on an outage but the agent path uses `recall_or_empty` so a
>   dead vector store costs recollections, not the reply; recall skips vectors
>   whose row is gone, so a leaked vector cannot resurrect a forgotten fact.
>
> - **2.3 (historical) Memory + preferences** — **preferences ✅, memory ❌.**
>   `workspace_preferences` (single row, migration `e5c1a7d24b83`) with
>   `GET`/`PATCH /preferences`, wired into the Settings page's new Workspace
>   panel. **The preferences actually change behavior** — `default_top_k` backs
>   RAG query/ask when a request omits `top_k`, `require_approval_by_default`
>   backs agent asks — with tests pinning that wiring, plus explicit-value-wins
>   tests. 6 tests. **Still missing: the `MemoryManager` facade and long-term
>   vector memory** (levels 3 of 6). `notifications_enabled` is stored but not
>   yet consulted by the dispatcher — it is currently decorative.
> - **2.4 Playwright e2e** ✅ **done** (2026-07-29). The blocker — "needs a
>   running stack (Ollama models, ~4.7 GB)" — was dissolved rather than worked
>   around: three zero-dependency providers (`LLM_PROVIDER=stub`,
>   `EMBEDDING_PROVIDER=stub`, `VECTOR_STORE_PROVIDER=memory`) let the real
>   backend run with no model server, no ChromaDB, and no network. All six
>   journeys pass in ~3 s, and CI gained a third job.
>   **Bounded on purpose:** the suite proves wiring, not answer quality — a stub
>   has none. 18 unit tests pin the stubs' determinism and structural validity
>   (the planner's real parser must accept the stub's JSON, the routing reply
>   must be a bare route word).
>   Two real defects surfaced while getting it green, both now fixed in the
>   config and documented in the testing guide: `next start` does not serve an
>   `output: "standalone"` build (pages render, then never hydrate — the suite
>   now runs the standalone server exactly as the Dockerfile does), and
>   `workers: 1` is required because a single shared workspace has no tenant
>   boundary to isolate parallel specs behind.

These are the "enterprise platform" claims that currently have no code. Order
matters: the tool registry is the keystone the others hang off.

### 2.1 Tool registry + marketplace (§19)

- `domain/interfaces/tool.py`: `Tool` protocol + `ToolMeta` (name, description,
  category, permissions, inputs, outputs, dependencies, version, origin).
- `app/tools/`: first native tools — `vector_search`, `web_search`,
  `create_task` — wrapping services that already exist.
- `platform/registry`: `ToolRegistry` + `@register_tool`, auto-discovered by the
  existing scanner.
- `GET /api/v1/tools` introspection endpoint + a marketplace UI page.
- `ToolMeta.permissions` is retained as **declarative metadata only** — there are
  no roles to check it against (§3). Keep the field: it documents what a tool
  touches, drives marketplace filtering, and is the enforcement point if
  accounts ever return. Do not build a permission checker that always passes.

### 2.2 Prompt registry + versioning (§18)

- `platform/prompts/`: Jinja2 template loader, `PromptRegistry`, `PROMPT_VERSION`
  table, active-version resolution.
- Migrate the existing per-agent `prompts.py` constants into templates.
- Record `prompt_version_id` on every `AiExecution` row → reproducibility.

### 2.3 MemoryManager facade + the two missing levels (§16)

- `app/memory/`: facade over the 4 existing stores; agents depend on it, not on
  stores directly.
- Long-term memory: `MEMORY_ENTRY` table + vector store namespace, durable facts.
- Preferences: a single workspace-scoped settings row (not per-user, per §3)
  + API → makes the Settings page actually save.

### 2.4 End-to-end tests (F5)

Playwright suite covering the six core journeys (upload→index, knowledge search,
grounded assistant answer, agent chat routing, planner→tasks, approval
pause/resume). No login step needed, which makes these materially simpler than
they would otherwise be. Wire into CI as a third job against `docker compose`.

**Exit criteria:** tool/prompt/memory registries introspectable via API and
visible in the UI; e2e suite green in CI.

---

## 7. Phase 3 — Headline features

> **3.1 Email agent ✅ DONE · 3.2 MCP ✅ DONE.** 3.3, 3.4, 3.5 not started.
>
> **3.1 Email agent** ✅ The full vertical:
> - `domain/interfaces/email.py` splits `EmailReader` from `EmailSender` — a
>   deployment can triage read-only without enabling the dangerous send path.
> - `infrastructure/email/` — IMAP + SMTP over the stdlib in worker threads (no
>   new dependency), with `parsing.py` isolating the genuinely tricky part:
>   encoded-word headers, multipart bodies, HTML-only fallback with script/style
>   stripped, unknown charsets, malformed dates. `BODY.PEEK` so fetching does not
>   silently mark mail read.
> - `agents/email/` — classify (9 intents + entity extraction, strict JSON with
>   layered parsing degrading to `OTHER`) → retrieve → draft. Spam is classified
>   and **stopped before drafting**; retrieval failure degrades to an ungrounded
>   draft rather than failing the message.
> - `features/emails/` — one row per message holding the classification,
>   entities, draft, and the human decision; `message_id` unique so re-syncing
>   cannot duplicate. Per-message failure isolation in sync.
> - Email Center UI: filter by state, inspect entities and the original message,
>   edit the draft inline, Send / Discard / Re-draft.
> - 45 tests (23 unit parsing + 22 integration). Both LLM calls carry prompt
>   provenance (`agent.email.classify` / `agent.email.draft`, v1).
>
> **Deviation from the plan, stated:** §3.1 said "→ the existing approval gate".
> I did **not** route drafts through the LangGraph `approval_gate`. That gate
> suspends a *graph run* and resumes it from a checkpoint; an email is a
> long-lived record that may sit for days and be edited before sending — a
> different lifecycle. The gate is explicit row state
> (`AWAITING_APPROVAL` → `send`/`discard`) instead. It is still strictly
> human-in-the-loop: `send` is the only code path that reaches SMTP, and a test
> asserts triage alone sends nothing. A failed send leaves the row decidable
> rather than claiming a reply that never left.
>
> **Unverified:** never run against a real IMAP/SMTP server. Parsing is tested
> against real RFC 5322 bytes built in-test; the transports are not.
>
> **3.2 MCP layer** ✅ `app/mcp/` in both directions:
> - **Consume** — `protocol.py` (JSON-RPC 2.0 framing, tolerant parsing of both
>   `inputSchema`/`input_schema` spellings and of servers that log to stdout),
>   `client.py` (`HttpMCPClient` + `StdioMCPClient`), `adapter.py`
>   (`MCPToolAdapter`, pydantic input models synthesized from the remote JSON
>   Schema, `origin="mcp"`), `registry.py` (`MCP_SERVERS` allow-list, startup
>   discovery, failure-isolated per server, `mcp__` name prefix so a remote tool
>   can never shadow a native one).
> - **Expose** — `server.py` + `POST /api/v1/tools/mcp` serving `initialize` /
>   `tools/list` / `tools/call` over the native tools. MCP-origin tools are
>   excluded so the endpoint never proxies back to another server.
> - 33 tests (26 unit + 7 integration). Marketplace UI shows the endpoint and
>   badges imported tools. Guide rewritten from "planned" to as-built.
> - **Not implemented, stated in the guide:** SSE transport, long-lived stdio
>   sessions (one process per call batch), and the resources/prompts primitives.
>   **Unverified against a real third-party MCP server** — tested against fakes
>   and its own endpoint only.
>
> Also completed out of order: **`notifications_enabled` is now functional** —
> the dispatcher consults it and fails *open* on a preference-read error, because
> losing an alert is worse than an extra one. It is no longer decorative.

## 7b. Phase 3 — remaining task list

### 3.1 Email agent (highest demo value)

The README already advertises it and every dependency exists — this is
assembly, not invention:

IMAP adapter (`domain/interfaces/email.py` + `infrastructure/email/imap.py`) →
9-intent classifier agent → entity extraction → RAG + conversation-history
retrieval → draft → **the existing approval gate** → SMTP send (the SMTP
notification provider is already written) → persist. New feature module
`features/emails/` + an Email Center UI page.

### 3.2 MCP layer (§8)

- `app/mcp/clients/` — stdio + HTTP/SSE transports, tool enumeration.
- `app/mcp/tools/MCPToolAdapter` — registers remote tools into the Phase-2
  `ToolRegistry` tagged `origin=mcp`, so agents call them identically.
- `mcp_servers.yaml` / `MCP_SERVERS` config + startup discovery hook.
- `app/mcp/servers/` — expose RAG query, document search, and task creation *as*
  an MCP server for external clients.
- Security: explicit server allow-list, per-tool permissions, all tool output
  treated as untrusted data (never as instructions).

### 3.3 RAG depth (§17)

OCR stage (Tesseract behind a provider port) → hybrid search (vector + keyword,
RRF fusion) → reranking → context compression to a token budget. Each a
swappable stage, each independently testable.

### 3.4 Workflow lifecycle (§20) + live status

`WORKFLOW_DEF` / `WORKFLOW_VERSION` tables with immutable `graph_spec`; runs pin
a `workflow_version_id`; rollback / clone / execution history. Then the
WebSocket manager (`app/ws/`, event-bus fan-out) and the visual builder UI.

### 3.5 Calendar agent + dashboard aggregate endpoint

Local-default calendar adapter with a Google adapter seam; single
`GET /api/v1/dashboard` replacing the frontend's three-call composition.

---

## 8. Phase 4 — Scale and ops (as needed)

- Redis event bus + Redis rate limiter → multi-replica correctness (F5).
- Postgres-backed LangGraph checkpointer → checkpoints survive restarts.
- `/metrics` endpoint (Prometheus) alongside the existing JSON logs.
- Diagram export pipeline (`scripts/export-diagrams`, Appendix B) — fills the
  missing `docs/diagrams/`.
- Secret hygiene: audit git history for keys before the repo goes public.

---

## 9. Sequencing summary

```
Phase 0  ✅ DONE      Green gates + auth removed
Phase 1  ✅ DONE      Deployable, honestly documented   (1.4 blocked: no credentials)
Phase 2  ✅ DONE      Tools ✅ · Prompts ✅ · Preferences ✅ · Memory ✅ · e2e ✅
Phase 3  ◐ PARTIAL    Email ✅ · MCP ✅ · RAG depth ❌ · Workflow lifecycle ❌
Phase 4  ☐ NOT STARTED Redis · Postgres checkpoints · metrics · diagrams
```

### Remaining work, in the order I would do it

| # | Item | Est. | Blocked by |
|---|---|---|---|
| 1 | Live cloud walkthrough incl. the S3 signature (§1.4) | 1 h | **Your credentials** |
| ~~2~~ | ~~`MemoryManager` facade + long-term vector memory (§2.3)~~ | ✅ **done** | — |
| ~~3~~ | ~~Consult `notifications_enabled` in the dispatcher~~ | ✅ **done** | — |
| ~~4~~ | ~~Playwright e2e, 6 journeys, CI job (§2.4)~~ | ✅ **done** | — |
| ~~5~~ | ~~Email agent — IMAP → classify → draft → approve → SMTP (§3.1)~~ | ✅ **done** | — |
| ~~6~~ | ~~MCP client + `MCPToolAdapter` + MCP server (§3.2)~~ | ✅ **done** | — |
| 7 | RAG depth: OCR, hybrid search, rerank, compression (§3.3) | 3–4 d | — |
| 8 | Workflow versioning / rollback / clone + WebSocket (§3.4) | 3–4 d | — |
| 9 | Prompt eval + promotion UI (deferred from 2.2) | 2 d | — |
| 10 | Phase 4 ops: Redis bus, Postgres checkpointer, `/metrics`, diagrams | 3 d | — |

Items 5–10 are each comparable in size to everything completed so far; they are
genuinely multi-day, not a final sprint.

Hard dependencies: **0 → everything**; **2.1 → 3.2** (MCP adapters need the tool
registry); **2.2 → nothing** (independent, can slip); **1.3 → 1.4** (verify the
durable path, not the ephemeral one).

## 10. Definition of done

- All six gates green in CI on every push.
- `DEPLOYMENT.md` followable by a stranger to a working deployment.
- Every capability claimed in `README.md` demonstrable in the running app — or
  removed from the README.
- Every `ARCHITECTURE.md` section either implemented, marked deferred, or marked
  **descoped by decision** (auth/RBAC) with a rationale — the convention the MCP
  guide already uses correctly.
- No dead authentication code anywhere: no JWT, no bearer headers, no
  refresh-token plumbing, no role checks that always pass.
- e2e suite covering the six core journeys, running in CI.
