# Feature Spec Summary: Version Endpoint

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 10 total (1 smoke, 0 regression)
**Assumptions**: 3 total (0 high / 0 medium / 3 low confidence)
**Review required**: Yes

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)

## Scope

This specification covers the addition of a read-only `/version` endpoint to the `api_test` service. The endpoint exposes three build-time-injected metadata fields (application version, git commit hash, and service name) via a GET request, and rejects all non-GET methods with a method-not-allowed response. It mirrors the existing `/uptime` and `/stats` endpoints in shape and access pattern (no auth, no database).

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 1 |
| Boundary conditions (@boundary) | 4 |
| Negative cases (@negative) | 5 |
| Edge cases (@edge-case) | 0 |

## Deferred Items

None.

## Open Assumptions (low confidence)

- **ASSUM-001**: Git commit hash format — assumed short 7-character hash; full SHA is the alternative.
- **ASSUM-002**: Response shape — assumed flat JSON object with no nesting, matching `/uptime` and `/stats`.
- **ASSUM-003**: JSON key naming — assumed exact lowercase keys `version`, `commit`, `service` without prefixes.

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "Version Endpoint" --context features/version-endpoint/version-endpoint_summary.md