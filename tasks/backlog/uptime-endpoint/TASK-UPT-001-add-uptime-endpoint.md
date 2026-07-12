---
id: TASK-UPT-001
title: Add GET /uptime endpoint
status: backlog
priority: high
task_type: feature
parent_review: TASK-REV-8e9b
tags:
- fastapi
- uptime
- observability
complexity: 3
wave: 1
implementation_mode: direct
dependencies: []
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Add GET /uptime endpoint

## Description

Expose service uptime at `GET /uptime` returning exactly three fields:
`service` (the configured app name from `settings.app_name`), `started_at`
(application process start time, UTC ISO-8601) and `uptime_seconds` (float,
sub-second precision). Mirror the structural shape of `src/health/` — a
dedicated `src/uptime/` module with its own `router.py` and `schemas.py`
(Pydantic response model), registered in `src/main.py`.

The start time is captured ONCE at application startup (module import /
process start) and is stable across requests; `uptime_seconds` is computed
per request as now minus start. The endpoint performs **no database access**
— `src/uptime/` must not import `src.db`.

Spec of record: `features/uptime-endpoint/uptime-endpoint.feature`
(5 scenarios) + `features/uptime-endpoint/uptime-endpoint_assumptions.yaml`
(ASSUM-001..003, all confirmed). Do not implement the PO document's extras
(no 503-degraded behaviour, no version field, no latency budget) — excluded
per ASSUM-001.

## Response Shape

```json
{
  "service": "api",
  "started_at": "2026-07-12T06:30:00.000000+00:00",
  "uptime_seconds": 1234.567
}
```

## Acceptance Criteria

- [ ] `src/uptime/__init__.py`, `src/uptime/router.py`, `src/uptime/schemas.py` exist; router registered in `src/main.py` with tag `uptime`
- [ ] `GET /uptime` returns 200 with exactly the three fields `service`, `started_at`, `uptime_seconds`
- [ ] `service` equals `settings.app_name`; `started_at` parses as ISO-8601 with UTC offset; `uptime_seconds` is a float >= 0
- [ ] Two sequential requests: second `uptime_seconds` > first; `started_at` identical in both
- [ ] `POST /uptime` returns 405 (method not allowed)
- [ ] `src/uptime/` contains no import of `src.db` (no database coupling) — asserted by a test
- [ ] Tests live in `tests/test_uptime.py` following the existing test conventions; full suite has zero net-new failures
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Capture start time as a module-level `datetime.now(timezone.utc)` in the
  uptime module (import-time capture = process start for this app shape);
  expose a helper so tests can reason about it. Do NOT re-capture per request.
- Mirror `src/health/router.py`'s APIRouter/prefix/tag conventions.
- No new dependencies. No settings changes required (reads existing
  `settings.app_name`).
