# Feature Spec Summary: User Creation Daily Counts

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 8 total (1 smoke, 0 regression)
**Assumptions**: 3 total (0 high / 0 medium / 3 low confidence)
**Review required**: Yes

## Scope

This specification covers the GET /users/created-per-day endpoint which returns the number of users created on each of the last 7 days, ordered oldest to newest. It includes happy-path, boundary, negative, and edge-case scenarios.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 2 |
| Boundary conditions (@boundary) | 2 |
| Negative cases (@negative) | 2 |
| Edge cases (@edge-case) | 2 |

## Deferred Items

None.

## Open Assumptions (low confidence)

- **ASSUM-001**: The response includes exactly 7 data points covering the most recent 7-day window. Basis: Inferred from request description; not explicitly stated in input.
- **ASSUM-002**: If fewer than 7 days of history exist, the endpoint returns 7 data points with zero counts for missing days. Basis: Inferred from common analytics API convention; not stated in input.
- **ASSUM-003**: The response format is a JSON array of objects, each containing a date string and a count integer. Basis: Inferred from request description 'JSON response containing the number of users created on each of the last 7 days'; exact structure not specified.

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)

## Verifier routing (proposed)

- "A request to the endpoint returns exactly 7 days of data ordered oldest to newest" → hurl
- "The endpoint returns data for exactly 7 days when 7 days of history exist" → hurl
- "The endpoint returns only the most recent 7 days when more than 7 days of history exist" → hurl
- "A POST request to the endpoint is rejected" → hurl
- "A request to a non-existent path returns a not-found response" → hurl
- "The endpoint returns 7 data points with zero counts when fewer than 7 days of history exist" → hurl
- "Concurrent requests to the endpoint return consistent data" → hurl
- "The response format is a JSON array of date-count pairs" → hurl

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "User Creation Daily Counts" --context features/created-per-day/created-per-day_summary.md