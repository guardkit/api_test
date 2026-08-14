---
complexity: 3
dependencies: []
feature_id: FEAT-UCNT
id: TASK-UCNT-001
implementation_mode: task-work
status: backlog
task_type: feature
title: Add GET /users/count endpoint
wave: 1
---

# Add GET /users/count endpoint

Expose the stored-user total at `GET /users/count` returning exactly
`{"count": <non-negative integer>}`. This extends the EXISTING users router
(`src/users/router.py`) — do not create a new package. Two constraints are
load-bearing:

1. **Route order:** the count route MUST be declared before the
   `GET /users/{user_id}` route in `src/users/router.py` (FastAPI matches in
   declaration order; declared after, the by-id pattern captures the literal
   segment `count` and fails UUID parsing with a 422). Existing routes must not
   change.
2. **Honest degradation (the pass-bar's mandatory negative path):** the count is
   data-bearing. When the database is unavailable, return **503 Service
   Unavailable** with a JSON body whose detail names the database as the cause —
   never a raw 500/stack trace, never a fabricated number. (Contrast
   `src/health/router.py`, which returns 200-with-degraded about its OWN status —
   that pattern is for health surfaces, not data surfaces.) Catch the DB error at
   this endpoint's seam only; do not change global error handling.

Implementation shape: add a `UserCountResponse` model (`count: int, ge=0`) in
`src/users/schemas.py`; a count query in `src/users/crud.py` (`SELECT count(*)`
via the existing AsyncSession patterns — reuse the module's conventions); the
route handler with `Depends(get_db)` mirroring the existing handlers' style.

## Acceptance Criteria
- [ ] GET /users/count returns 200 with exactly the key `count`, a non-negative integer equal to the number of stored users; with an empty store it returns `{"count": 0}`
- [ ] Creating a user then re-requesting the count shows the count incremented by one (the seeded-data round-trip)
- [ ] GET /users/{user_id} for an existing user still returns that user (route-order regression guard), and the full existing test suite stays green
- [ ] POST/PUT/DELETE to /users/count are rejected as unsupported (405)
- [ ] With the database unavailable, GET /users/count returns 503 with a JSON detail naming the database as the cause (no raw 500, no stack trace)
- [ ] Tests in tests/users/ cover all of the above using the app's existing test-client and DB-fixture patterns (mirror tests/users/test_router.py conventions)
