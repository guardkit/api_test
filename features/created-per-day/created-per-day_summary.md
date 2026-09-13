# Feature Spec Summary: User Creation Analytics - Daily Counts

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 6 total (1 smoke, 0 regression)
**Assumptions**: 2 total (0 high / 0 medium / 2 low confidence)
**Review required**: Yes

## Scope

This specification covers the GET /users/created-per-day endpoint which returns the number of users created on each of the last 7 days, ordered oldest to newest. It defines the happy-path, boundary conditions for system uptime, negative cases for service availability, and edge-case handling for systems running less than 7 days.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 1 |
| Boundary conditions (@boundary) | 2 |
| Negative cases (@negative) | 2 |
| Edge cases (@edge-case) | 1 |

## Deferred Items

None.

## Open Assumptions (low confidence)

- **ASSUM-001**: The endpoint returns exactly 7 data points covering the most recent 7-day window. Basis: Inferred from request description; not explicitly stated whether the window is rolling or fixed.
- **ASSUM-002**: If the system has been running for less than 7 days, the endpoint returns 7 data points with zero counts for missing days. Basis: Open question in input; no explicit decision on how to handle short-running systems.

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "User Creation Analytics - Daily Counts" --context features/created-per-day/created-per-day_summary.md

## Verifier routing (proposed)

- "A request to the daily counts endpoint returns exactly 7 days of data ordered oldest first" → hurl
- "The endpoint returns exactly 7 days of data when the system has been running for at least 7 days" → hurl
- "The endpoint returns exactly 7 days of data when the system has been running for more than 7 days" → hurl
- "A request to a non-existent endpoint returns a failure" → hurl
- "The endpoint returns a failure when the service is unavailable" → hurl
- "The endpoint returns 7 data points even when the system has been running for less than 7 days" → hurl

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)