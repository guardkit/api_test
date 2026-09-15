# Feature Spec Summary: User Creation Analytics - Daily Counts

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 7 total (1 smoke, 0 regression)
**Assumptions**: 2 total (0 high / 0 medium / 2 low confidence)
**Review required**: Yes

## Scope

This specification covers the GET /users/created-per-day endpoint which returns the number of users created on each of the last 7 days, ordered oldest to newest. It defines the happy-path response shape, boundary conditions for the 7-day window, negative cases for unsupported methods and empty data, and edge cases for concurrency and partial-day data.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 1 |
| Boundary conditions (@boundary) | 2 |
| Negative cases (@negative) | 3 |
| Edge cases (@edge-case) | 2 |

## Deferred Items

None.

## Open Assumptions (low confidence)

- **ASSUM-001**: The response includes the current day as the most recent entry. Basis: Inferred from 'last 7 days' phrasing; not stated whether current day is included or only completed days.
- **ASSUM-002**: The response includes exactly seven data points. Basis: Inferred from 'exactly 7 data points' constraint; not stated how to handle periods with fewer than 7 days of data.

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)

## Verifier routing (proposed)

- "A request for daily counts returns exactly seven days ordered oldest to newest" → hurl
- "The endpoint returns exactly seven days of data" → hurl
- "The endpoint does not return fewer than seven days of data" → hurl
- "A POST request to the endpoint is rejected" → hurl
- "The endpoint returns seven days of zero counts when no users were created" → hurl
- "Two simultaneous requests both return the same seven-day window" → toolchain
- "The endpoint includes the current day even if it is incomplete" → hurl

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "User Creation Analytics - Daily Counts" --context features/created-per-day/created-per-day_summary.md