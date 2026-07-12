---
id: TASK-REV-F2ST
title: "Plan: Service Request Statistics Endpoint"
status: review_complete
priority: high
task_type: review
created: "2026-07-12T13:52:00Z"
completed: "2026-07-12T13:58:00Z"
decision: implement
clarification:
  context_a:
    timestamp: "2026-07-12T13:52:00Z"
    decisions:
      focus: all
      tradeoff: balanced
    note: "--no-questions (rung-B headless, Factory-2); defaults applied"
  context_b:
    timestamp: "2026-07-12T13:58:00Z"
    decisions:
      approach: option_1_middleware_counter
      execution: sequential
      testing: standard
    note: "--no-questions; recommended option auto-selected mechanically"
---

# Plan: Service Request Statistics Endpoint

**Source spec:** `features/stats-endpoint/stats-endpoint_summary.md` (8 scenarios, 4
low-confidence assumptions — rung-B `--auto` spec from Mode P handoff
`feature_spec_inputs/2dfb4ef5-b769-4a89-91b6-f25498af0090.md`).

## Technical options analysis

**Option 1: ASGI middleware counter + in-process stats state + own router (RECOMMENDED)**
- Complexity: 4/10 · Effort: 1–2 h
- A `StatsState` module-level object (thread-safe increment; `count: int`,
  `first_request_at: datetime | None`) updated by a small ASGI middleware registered in
  `src/main.py` (the repo already carries three middleware — established pattern); a
  `src/stats/` module mirroring `src/health/` (router + Pydantic response schema); no
  database access anywhere in the path.
- Pros: counts every handled request per ASSUM-003 (middleware layer sees all); mirrors the
  /health module convention the request names; trivially testable with TestClient.
- Cons: one more middleware in the stack (ordering note: register outermost-first is not
  required — count-on-entry is sufficient for the spec's observable behaviour).

**Option 2: Count inside a router dependency**
- Complexity: 3/10 — but only counts routed requests that use the dependency; misses 404s
  and other handled requests → fails ASSUM-003's plain reading. Rejected.

**Option 3: Fold counting into the existing RequestLoggingMiddleware**
- Complexity: 3/10 — entangles logging with statistics; the two middleware tests already
  failing in the baseline make this seam riskier to touch (zero-net-new bar). Rejected.

## Decision

**Option 1**, auto-selected (rung-B mechanical: recommended option). Single task —
the feature is one cohesive vertical slice (state + middleware + schema + router + tests),
matching the Factory-1 single-task precedent (TASK-UPT-001).

## Risk notes

- The counter middleware must NOT touch the two baseline-failing middleware tests'
  surfaces (`CorrelationIDMiddleware` internals untouched; new middleware added alongside).
- DB-unavailable edge scenario is unit-testable (no DB dependency in the stats path).
- Restart-reset (process-lifetime) is inherent to in-process state; the restart scenario
  is exercised by constructing a fresh app instance in tests.
