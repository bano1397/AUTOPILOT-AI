# API Guide

The backend exposes a versioned REST API under `/api/v1`. Interactive
OpenAPI docs are served at **`/docs`** (Swagger) and **`/redoc`** when the
server is running.

## Conventions

- **Response envelope.** Business endpoints return
  `{ "success": true, "data": <payload>, "meta": <pagination|null> }`; errors
  return `{ "success": false, "error": { "code", "message", "details" } }`.
  Infrastructure probes (`/health`, `/health/ready`) return raw payloads.
- **Auth.** Send `Authorization: Bearer <access_token>`. Access tokens are
  short-lived; the refresh token is delivered as an httpOnly cookie (browsers)
  and also in the login/refresh response body (other clients).
- **Pagination.** List endpoints accept `?page=` and `?page_size=` (≤100) and
  return `meta: { page, page_size, total, pages }`.
- **Errors.** Standard codes include `VALIDATION_ERROR` (422),
  `AUTHENTICATION_FAILED` (401), `PERMISSION_DENIED` (403), `NOT_FOUND` (404),
  `CONFLICT` (409), `RATE_LIMITED` (429), `UPSTREAM_SERVICE_ERROR` (502).

## Endpoint summary

| Area | Method & path | Notes |
|---|---|---|
| System | `GET /health`, `GET /health/ready` | Liveness / readiness (DB probe) |
| Auth | `POST /api/v1/auth/register` | Rate-limited |
| | `POST /api/v1/auth/login` | Sets refresh cookie |
| | `POST /api/v1/auth/refresh` | Cookie or body token |
| | `POST /api/v1/auth/logout` | Revokes + clears cookie |
| | `GET /api/v1/auth/me` | Current user |
| Users (admin) | `GET /api/v1/users`, `GET /api/v1/users/{id}` | Paginated |
| Documents | `POST /api/v1/documents` | Multipart upload → async ingest |
| | `GET /api/v1/documents`, `GET /{id}`, `DELETE /{id}` | Owner-scoped |
| RAG | `POST /api/v1/rag/query` | Cited semantic search |
| | `POST /api/v1/rag/ask` | Grounded answer + sources |
| Agents | `GET /api/v1/agents` | Registered agents |
| | `POST /api/v1/agents/ask` | Supervisor graph; `require_approval` opt |
| Conversations | `GET /api/v1/conversations`, `GET /{id}` | Threads + messages |
| Workflows | `GET /api/v1/workflows/runs`, `GET /runs/{id}` | Runs + step timelines |
| Approvals | `GET /api/v1/approvals` | Pending review |
| | `POST /api/v1/approvals/{id}/decision` | approve / reject → resume |
| Notifications | `GET /api/v1/notifications`, `GET /unread-count` | |
| | `POST /{id}/read`, `POST /read-all` | |
| Scheduler (admin) | `GET /api/v1/scheduler/jobs` | |
| | `POST /jobs/{id}/{run,pause,resume}` | |
| Tasks | `GET/POST /api/v1/tasks`, `PATCH/DELETE /{id}` | `?status=` filter |
| Analytics | `GET /api/v1/analytics/overview?days=` | Usage/cost aggregation |

## Example

```bash
# Register, then log in (cookie stored by -c).
curl -sX POST localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"me@example.com","password":"supersecret1"}'

TOKEN=$(curl -sX POST localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"me@example.com","password":"supersecret1"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['data']['access_token'])")

curl -s localhost:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN"
```
