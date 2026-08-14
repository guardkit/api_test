---
complexity: 2
dependencies: []
feature_id: FEAT-UBEM
id: TASK-UBEM-001
implementation_mode: task-work
status: design_approved
task_type: feature
title: Add GET /users/by-email endpoint
wave: 1
---

# Add GET /users/by-email endpoint

Expose the existing email lookup as `GET /users/by-email?email=<address>`:
200 with that user's `UserPublic` record, 404 when no user has the address,
422 on a malformed address, 503 naming the database when it is down. Three
constraints are load-bearing:

1. **Reuse, don't rewrite:** the query is `crud.get_user_by_email` (src/users/crud.py
   — already shipped; the create path's duplicate check uses it). This task adds the
   route and its response semantics ONLY. No new query code, no new schema (the
   response is the existing `UserPublic`).
2. **Route order (the FEAT-UCNT precedent):** the literal `by-email` route MUST be
   declared in `src/users/router.py` BEFORE the `GET /users/{user_id}` route —
   declared after, the by-id pattern captures the literal segment `by-email` and
   fails UUID parsing with a 422. Existing routes must not change.
3. **Validation + honest degradation:** the email rides a query parameter typed
   `EmailStr` (pydantic), so a malformed address 422s before any query runs. No
   match → 404 with a clear detail (mirror the by-id route's not-found shape).
   Database unavailable → **503** with a JSON detail naming the database as the
   cause (the exact convention `GET /users/count` established — mirror its handler
   seam; never a raw 500, never global error-handling changes). Lookup is EXACT
   MATCH as `crud.get_user_by_email` applies it today — no case-normalization.

## Acceptance Criteria
- [ ] GET /users/by-email?email=<existing> returns 200 with that user's UserPublic record (id + email)
- [ ] With several users stored, the lookup returns exactly the matching user
- [ ] GET /users/by-email?email=<unknown> returns 404 with a clear detail; a malformed address returns 422 without touching the database
- [ ] GET /users/{user_id} for an existing user still returns that user (route-order regression guard), and the full existing test suite stays green
- [ ] With the database unavailable, the route returns 503 with a JSON detail naming the database as the cause
- [ ] Tests in tests/users/ cover all of the above using the existing test-client and DB-fixture patterns (mirror the FEAT-UCNT tests' conventions)