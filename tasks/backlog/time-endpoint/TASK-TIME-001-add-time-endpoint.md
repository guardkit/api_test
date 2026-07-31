---
complexity: 2
dependencies: []
feature_id: FEAT-TIME
id: TASK-TIME-001
implementation_mode: task-work
status: backlog
task_type: feature
title: Add GET /time endpoint
wave: 1
conformance:
  ac_paths: true
  rules:
    - id: R-TIME-ROUTE
      type: token_coverage
      paths: ["src/time/router.py"]
      require_tokens: ["/time", "router.get"]
    - id: R-TIME-WIRED
      type: token_coverage
      paths: ["src/main.py"]
      require_tokens: ["time_router"]
    - id: R-TIME-TESTS
      type: token_coverage
      paths: ["src/time/router.py"]
      require_tokens: []
      require_test_tokens:
        paths: ["tests/time/*.py"]
        tokens: ["/time", "200", "405"]
---

# Add GET /time endpoint

Expose the server's current clock as `GET /time`: 200 with a JSON body of
exactly two fields — `"time"` (current UTC, ISO-8601, second precision,
trailing `Z`, e.g. `"2026-07-31T12:34:56Z"`) and `"service"` (`"api_test"`).
Write methods 405. No database involvement of any kind.

Constraints, all load-bearing:

1. **Module home (the house pattern):** a new `src/time/` package —
   `router.py` + `schemas.py` — mirroring `src/version/` exactly (APIRouter,
   response_model, tags, summary/description, documented responses). Wire it
   in `src/main.py` as `from src.time.router import router as time_router`
   plus one `include_router` line beside the existing ones. Rooted `src.`
   imports mean the package name cannot shadow the stdlib `time` module;
   inside the new files use `datetime` (never the stdlib `time` module) so
   the question never even arises.
2. **Honest clock:** the value is `datetime.now(timezone.utc)` computed in
   the request handler — never a module-level constant, never cached, never
   a naive datetime. Serialize to second precision with the trailing `Z`
   (truncate/replace microseconds; render `+00:00` as `Z`).
3. **Exactly two fields:** the response model is a new `TimeResponse` schema
   (two fields, no extras). The freshness scenario is the anti-stub tooth —
   tests MUST include the two-requests-ordering check.
4. **No DB surface:** import nothing from `src/db`; no session dependency.
   The database-down scenario is proven as an UNAFFECTED 200 (see the
   feature's negative scenario) — tests express it by exercising the route
   with no database fixture at all (the route works in a bare TestClient).
5. **Tests home:** `tests/time/` (new dir), covering: 200 + exactly-two-fields
   + ISO shape with `Z`; freshness/ordering across two calls; 405 for
   POST/PUT/DELETE; the bare-client (no DB fixture) 200.

NOTE (factory receipt, no action needed by the Player): this task carries a
`conformance:` block (frontmatter above — FEAT-SCG machinery). With durable
receipts now live, this build's conformance receipt is the factory's first
that SURVIVES the worktree. The rules are deliberately modest textual checks;
the behavioral teeth stay in the pass-bar tests.

## Acceptance Criteria
- [ ] GET /time returns 200 with a JSON body of exactly two fields: "time" and "service"
- [ ] "time" is current UTC in ISO-8601 second precision with a trailing "Z"; "service" is "api_test"
- [ ] Two GET /time calls at least one second apart return strictly increasing timestamps (freshness is real)
- [ ] POST, PUT and DELETE on /time each return 405
- [ ] The route imports nothing from src/db and returns 200 with no database available (bare TestClient test)
- [ ] src/main.py wires the router as time_router; existing routes are untouched
- [ ] Tests live in tests/time/ and cover every criterion above
