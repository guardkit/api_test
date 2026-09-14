# Feature Spec Summary: User Creation Daily Counts

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 6 total (1 smoke, 0 regression)
**Assumptions**: 2 total (0 high / 0 medium / 2 low confidence)
**Review required**: Yes

## Scope

This specification covers the GET /users/created-per-day endpoint which returns the number of users created on each of the last 7 days, ordered oldest first. It includes happy-path, boundary, negative, and edge-case scenarios.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 1 |
| Boundary conditions (@boundary) | 2 |
| Negative cases (@negative) | 1 |
| Edge cases (@edge-case) | 2 |

## Deferred Items

None.

## Open Assumptions (low confidence)

- **ASSUM-001**: The response includes exactly 7 data points for the last 7 days. Basis: Inferred from request description; not explicitly stated in input.
- **ASSUM-002**: The 7-day window is inclusive of the oldest day. Basis: Inferred from 'last 7 days' phrasing; could be exclusive or inclusive.

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)

## Verifier routing (proposed)

- "Requesting the daily user counts returns exactly seven days of data ordered oldest first" → hurl
- "The oldest day in the 7-day window is included in the response" → hurl
- "The most recent day is included in the response" → hurl
- "The endpoint rejects non-GET requests" → hurl
- "The endpoint returns zero counts when no users were created in the last 7 days" → hurl
- "The endpoint fails gracefully when the user database is unavailable" → hurl

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "User Creation Daily Counts" --context features/get-users-created-per-day/get-users-created-per-day_summary.md