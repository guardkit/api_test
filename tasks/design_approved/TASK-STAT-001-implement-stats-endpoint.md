---
complexity: 4
created: '2026-07-12T13:58:00Z'
dependencies: []
feature_id: FEAT-STAT
id: TASK-STAT-001
implementation_mode: task-work
parent_review: TASK-REV-F2ST
priority: high
status: design_approved
tags:
- fastapi
- statistics
- observability
- middleware
task_type: feature
title: Add GET /stats endpoint with in-process request counter
wave: 1
---

# Add GET /stats endpoint with in-process request counter

Implement the Service Request Statistics Endpoint exactly per
`features/stats-endpoint/stats-endpoint.feature` (8 scenarios) and its assumptions manifest.
Approach = review Option 1 (TASK-REV-F2ST): ASGI middleware counter + in-process state +
own router mirroring the `/health` module structure.

## Scope

- `src/stats/` module: Pydantic response schema (`service: str`, `requests_served: int`,
  `first_request_at: str | None` — UTC ISO-8601 when set) + APIRouter exposing `GET /stats`.
- A small ASGI middleware (own module under `src/stats/` or `src/middleware/` following repo
  convention) that increments a thread-safe in-process `StatsState` on every handled HTTP
  request and records the first-request time (UTC) once.
- Register the middleware + router in `src/main.py` alongside the existing three middleware
  and three routers. Do NOT modify `CorrelationIDMiddleware`, `RequestLoggingMiddleware`,
  `APIVersionHeaderMiddleware`, or any existing endpoint/test.
- No database access anywhere in the stats path (no session dependency imported).
- Tests under `tests/` following the repo's existing structure (see `tests/test_uptime.py`
  precedent): cover every acceptance criterion below, hermetically (TestClient; fresh app
  instance where the zero-history/restart scenarios need one).

## Acceptance Criteria

- [ ] AC-1: `GET /stats` returns success with a JSON body containing exactly the three fields `service` (string), `requests_served` (integer) and `first_request_at` (UTC ISO-8601 string or null).
- [ ] AC-2: `service` equals the configured application name from the same settings source `/health` uses.
- [ ] AC-3: `requests_served` is strictly greater on a second `GET /stats` than on the first (the counter counts).
- [ ] AC-4: `first_request_at` is identical across successive responses once set, and parses as UTC ISO-8601.
- [ ] AC-5: On a freshly constructed app, the first `GET /stats` response reports `requests_served >= 1` and a non-null `first_request_at` (ASSUM-002: the in-flight statistics request is included in its own count).
- [ ] AC-6: Every handled HTTP request increments the counter regardless of route or outcome — a request to an existing non-stats endpoint and a request yielding a client error both increase `requests_served` (ASSUM-003, middleware-level counting).
- [ ] AC-7: `POST /stats` is rejected as method-not-allowed.
- [ ] AC-8: The stats path performs no database access — stats tests pass with the database dependency absent/monkeypatched, and `src/stats/` imports no session/engine machinery.
- [ ] AC-9: The full existing test suite stays green: zero net-new failures vs the 170-passed/2-known-failed baseline (`qa/known-failures.yaml`), with the new tests green.
- [ ] AC-10: All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

Unit/integration tests via FastAPI TestClient, hermetic (no live services, no env
dependence). The suite invocation of record for the zero-net-new check:
`DATABASE_URL="postgresql+asyncpg://postgres:test@localhost:5433/test" .venv/bin/python -m pytest -q --forked`

## Coach Validation Commands

- `.venv/bin/python -m pytest tests/ -q --forked -k "stats"` — new tests green
- Full suite (invocation above) — zero net-new vs `qa/known-failures.yaml`

## Seam Tests

Boundary = ASGI middleware ↔ router state sharing: at least one test asserts the router
reads the SAME state object the middleware writes (e.g. non-stats traffic then `GET /stats`
reflects it — AC-6 doubles as this seam test).