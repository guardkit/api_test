---
id: TASK-REV-8e9b
title: Plan: Service Uptime Endpoint
priority: high
status: backlog
task_type: review
---

# Plan: Service Uptime Endpoint

## Review Scope

Plan: Service Uptime Endpoint

## Objective

Analyze and produce findings/recommendations; this task carries no implementation.

## Acceptance Criteria

- [ ] Review report generated at .claude/reviews/TASK-REV-8e9b-review-report.md
- [ ] Decision checkpoint completed ([A]ccept / [R]evise / [I]mplement / [C]ancel)

## Decision Review (executed 2026-07-12, attended — Factory-1 pass; scope: technical, trade-off: balanced)

**Context**: BDD spec of record `features/uptime-endpoint/uptime-endpoint.feature` (5 scenarios,
3 confirmed assumptions); source request = Mode P handoff `feature_spec_inputs/41a2e3ef-….md`
(request text verbatim; PO extras excluded per ASSUM-001).

### Options analysis

**Option 1 — dedicated `src/uptime/` module mirroring `src/health/` (RECOMMENDED)**
Complexity 3/10, ~30-45 min. Own router + `schemas.py` + tests; `started_at` captured once at
process start; `uptime_seconds` computed per request. Pros: matches the request VERBATIM ("own
router + Pydantic response schema + tests", "same module structure as /health"); proven repo
pattern; no DB coupling by construction. Cons: none material at this size.

**Option 2 — add an /uptime route inside `src/health/`**
Complexity 2/10. Fewer files. REJECTED: violates the request's explicit "own router" instruction.

**Option 3 — metrics-style exposure (middleware / /metrics)**
Complexity 5/10. REJECTED: over-engineering for the stated need; changes the observable contract.

### Decision
**[I]mplement Option 1** — pre-authorized by Rich (Context A/B batched: focus=technical,
tradeoff=balanced, approach=mirror-health, execution=auto, testing=standard). One task
(complexity 3, wave 1, direct mode — the proven FEAT-9E59 shape). BDD @task tagging SKIPPED
deliberately: pytest-bdd is not an api_test dependency, so the R2 runner would be dormant;
scenarios remain the human-readable spec of record (recorded in the Factory-1 record).

clarification:
  context_a: {focus: technical, tradeoff: balanced}
  context_b: {approach: option-1-mirror-health, execution: auto, testing: standard}
  checkpoint: implement (pre-authorized, attended)
