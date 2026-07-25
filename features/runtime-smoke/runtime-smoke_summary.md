# Feature Spec Summary: Runtime smoke — seeded round-trip against a sandboxed deployment

**Stack**: python
**Generated**: 2026-07-25T10:09:05Z
**Scenarios**: 12 total (2 smoke, 1 regression)
**Assumptions**: 8 total (0 high / 0 medium / 8 low confidence)
**Review required**: Yes — REVIEW REQUIRED: all assumptions unconfirmed (--auto mode); Rich's curation lands as a dated commit into runtime-smoke_assumptions.yaml

## Scope

The factory's first layer-3 runtime verification surface: deploy the freshly built app image
into a sandboxed throwaway compose stack (project `apitest-smoke`, internal-only zero-egress
networks, hardened non-root app container, pre-built image only), seed Postgres directly with
a per-run marker, and verify through the running service that the seeded data round-trips, a
created user reads back identically, and not-found/conflict/validation failures are reported
honestly — from an in-network stdlib probe container. Lands as the independent behavioural
oracle `tests/acceptance/users_roundtrip.py`, which guardkit's existing oracle machinery
discovers and runs on every subsequent build (moves M3: 0 → 1; instruments M2).

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 3 |
| Boundary conditions (@boundary) | 2 |
| Negative cases (@negative) | 4 |
| Edge cases (@edge-case) | 3 |

## Deferred Items

None. Edge-case expansion skipped (--auto); the active egress-attempt probe is explicitly
deferred to a later version via ASSUM-007 (v1 verification is configuration-level).

## Open Assumptions (low confidence)

ASSUM-001 (smoke image tag + host-build-only-when-missing) · ASSUM-002 (per-run marker shape +
psql-in-container seeding) · ASSUM-003 (300s budget / 120s health wait) · ASSUM-004
(python:3.12-slim stdlib probe container) · ASSUM-005 (negative probe set) · ASSUM-006
(project apitest-smoke isolation) · ASSUM-007 (config-level egress verification) · ASSUM-008
(single pytest oracle file with JSON verdict).

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "Runtime smoke — seeded round-trip against a sandboxed deployment" \
      --context features/runtime-smoke/runtime-smoke_summary.md \
      --context docs/runtime-smoke-scope-and-buildplan.md \
      --context docker-compose.yml \
      --context deploy/docker-compose.candidate.yml \
      --context src/main.py
