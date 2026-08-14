---
complexity: 3
dependencies: []
feature_id: FEAT-UPT1
id: TASK-UPT-001
implementation_mode: task-work
status: backlog
task_type: feature
title: Add GET /uptime endpoint
wave: 1
---

# Add GET /uptime endpoint

Expose service uptime at GET /uptime returning `{"service": <name>, "started_at":
<ISO8601 UTC>, "uptime_seconds": <float>}`. Mirror the existing version endpoint's
structure exactly: a `src/uptime/` package with `router.py` (APIRouter, prefix set in the
router, tagged "uptime"), wired into `src/main.py` beside the version router (see
`from src.version.router import router as version_router` and its `include_router` call).
Record process start time at module import using a monotonic-clock pair (wall-clock
`started_at` captured once; `uptime_seconds` computed per-request from `time.monotonic()`
delta so it never goes backwards). No database, no auth, no config — read-only metadata,
the same posture as /version and /health.

## Acceptance Criteria
- [ ] GET /uptime returns 200 with exactly the keys service, started_at, uptime_seconds; started_at is a valid ISO8601 UTC timestamp and stable across requests; uptime_seconds is a non-negative float that strictly increases between two sequential requests in a test (allowing a small sleep)
- [ ] The router lives in src/uptime/router.py mirroring src/version/ structure and is wired in src/main.py with tags=["uptime"]; no other existing routes change (the full existing test suite stays green)
- [ ] Tests in tests/uptime/ cover: 200 + key shape, started_at stability, uptime monotonicity; they use the app's existing test-client pattern (mirror the tests for /version)
