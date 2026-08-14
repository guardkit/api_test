---
id: TASK-REV-RSMK
title: "Plan: Runtime smoke — seeded round-trip against a sandboxed deployment"
task_type: review
priority: high
status: review_complete
mode: decision
depth: standard
created: 2026-07-25T10:20:00Z
clarification:
  context_a: skipped (--no-questions; coordinator-run rung B)
  context_b: skipped (--no-questions; defaults)
---
# Decision review — implementation approach for the runtime smoke

Contexts read: features/runtime-smoke/runtime-smoke_summary.md ·
docs/runtime-smoke-scope-and-buildplan.md · docker-compose.yml ·
deploy/docker-compose.candidate.yml · src/main.py (+ src/users/models.py, router.py grounding).

## Options

**Option 1 — Standalone smoke compose + self-contained pytest oracle + in-network stdlib probe
container (RECOMMENDED, 88/100).** A new `deploy/docker-compose.smoke.yml` (project
`apitest-smoke`, two internal-only networks, hardened app service, pre-built image), a seed
template + stdlib probe script under `qa/smoke/`, and one pytest file
`tests/acceptance/users_roundtrip.py` that orchestrates deploy → seed → probe → teardown.
Pros: matches the scope doc verbatim; lands exactly on guardkit's oracle-discovery convention;
zero changes to existing surfaces; probe independence (separate container, zero egress). Cons:
oracle owns docker orchestration (subprocess complexity).

**Option 2 — Probe via docker exec inside the app container (72/100).** No probe container;
curl from within the app. Pros: fewer moving parts. Cons: probes execute inside the untrusted
freshly-built image — the artifact under test hosts its own examiner; weaker honesty.

**Option 3 — Extend the qa/gates F4 engine to multi-step POST sequences (55/100).** Pros:
reuses the registered-gate surface. Cons: the stdlib gate engine is single-GET by design;
a multi-step stateful round-trip is a different shape; larger blast radius; does not land on
the `tests/acceptance/*_roundtrip.py` oracle convention that fills `behavioural_oracle`.

## Decision

Option 1, auto-selected (coordinator-run, Rich's standing yes; same rung-B shape as the
FEAT-AE43 stats run). Three tasks, two waves. Testing depth: standard.
