# Feature Spec Summary: User Creation Analytics - Daily Counts

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 7 total (1 smoke, 0 regression)
**Assumptions**: 3 total (0 high / 0 medium / 3 low confidence)
**Review required**: Yes

## Scope

This specification covers the GET /users/created-per-day endpoint which returns the number of users created on each of the last 7 days, ordered from oldest to newest. It defines the happy-path response shape, boundary conditions for the 7-day window, negative cases for invalid methods and empty data, and edge cases for JSON validity and strict date ordering.

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

- **ASSUM-001**: The response body is a JSON array of objects with "date" and "count" keys. Basis: Inferred from request description; exact JSON structure not specified.
- **ASSUM-002**: The endpoint always returns exactly 7 data points. Basis: Request states "last 7 days" but does not specify behavior when history is shorter.
- **ASSUM-003**: When no users were created, the endpoint returns 7 days with zero counts. Basis: Inferred from "last 7 days" requirement; not explicitly stated for empty periods.

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)

## Verifier routing (proposed)

- "A request to the daily counts endpoint returns the last 7 days of data" → hurl
- "The endpoint returns exactly 7 days of data regardless of total history" → hurl
- "The endpoint does not return more than 7 days of data" → hurl
- "The endpoint returns 7 days with zero counts when no users were created" → hurl
- "A POST request to the daily counts endpoint is rejected" → hurl
- "The response is valid JSON" → hurl
- "The data points are strictly ordered from oldest to newest" → hurl