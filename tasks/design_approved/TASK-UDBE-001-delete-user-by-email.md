---
complexity: 2
conformance:
  ac_paths: true
  rules:
  - id: R-UDBE-ROUTE
    paths:
    - src/users/router.py
    require_tokens:
    - /by-email
    - router.delete
    type: token_coverage
  - id: R-UDBE-TESTS
    paths:
    - src/users/router.py
    require_test_tokens:
      paths:
      - tests/users/*.py
      tokens:
      - by-email
      - '204'
      - '404'
      - '503'
    require_tokens: []
    type: token_coverage
dependencies: []
feature_id: FEAT-UDBE
id: TASK-UDBE-001
implementation_mode: task-work
status: design_approved
task_type: feature
title: Add DELETE /users/by-email endpoint
wave: 1
---

# Add DELETE /users/by-email endpoint

Expose deletion by email as `DELETE /users/by-email?email=<address>`: 204 empty
body on success, 404 when no user has the address, 422 on a malformed address,
503 naming the database when it is down. Three constraints are load-bearing:

1. **Reuse, don't rewrite:** the lookup is `crud.get_user_by_email`
   (src/users/crud.py:79) and the deletion is `crud.delete_user`
   (src/users/crud.py:122) — both already shipped. This task adds the route and
   its response semantics ONLY. No new query code, no schema changes.
2. **Route order (the FEAT-UCNT/UBEM precedent, now in the DELETE group):** the
   literal `by-email` DELETE route MUST be declared in `src/users/router.py`
   BEFORE the `DELETE /users/{user_id}` route — declared after, the by-id
   pattern captures the literal segment and fails UUID parsing with a 422.
   Existing routes must not change.
3. **Validation + honest semantics:** the email rides a query parameter typed
   `EmailStr` (pydantic), so a malformed address 422s before any query runs.
   Success mirrors the by-id delete exactly: `Response(status_code=204)`, empty
   body. No match → 404 with a clear detail (the absence reported honestly — a
   second delete of the same email is a 404, never a fabricated 204). Database
   unavailable → **503** with a JSON detail naming the database as the cause
   (the exact `GET /users/count` convention — mirror its handler seam; never a
   raw 500, never global error-handling changes). Match is EXACT as
   `crud.get_user_by_email` applies it today — no case-normalization. Deletion
   is the hard delete `crud.delete_user` performs today.

NOTE (factory receipt, no action needed by the Player): this task carries the
factory's FIRST `conformance:` block (frontmatter above — FEAT-SCG machinery).
The rules are deliberately modest textual checks; the behavioral teeth stay in
the pass-bar tests. If the chain snapshots and evaluates them, that receipt is
the block's purpose.

## Acceptance Criteria
- [ ] DELETE /users/by-email?email=<existing> returns 204 with an empty body, and a subsequent GET /users/by-email for the same address returns 404 (the deletion round-trip is real)
- [ ] With several users stored, deleting by email removes exactly the matching user; the others remain retrievable
- [ ] DELETE /users/by-email?email=<unknown> returns 404 with a clear detail; deleting the same email twice returns 404 the second time; a malformed address returns 422 without touching the database
- [ ] DELETE /users/{user_id} for an existing user still returns 204 (route-order regression guard: the literal route is declared before the parameterized route in the DELETE group), and the full existing test suite stays green
- [ ] With the database unavailable, the route returns 503 with a JSON detail naming the database as the cause
- [ ] Tests in tests/users/ cover all of the above using the existing test-client and DB-fixture patterns (mirror the FEAT-UBEM tests' conventions)