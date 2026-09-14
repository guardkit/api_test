# Feature Spec Summary: Daily User Creation Count

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 7 total (1 smoke, 0 regression)
**Assumptions**: 3 total (0 high / 0 medium / 3 low confidence)
**Review required**: Yes

## Scope

This specification covers the GET /users/created-per-day endpoint which returns the number of users created on each of the last 7 days, ordered oldest to newest. It defines the happy-path 7-day window, boundary conditions for window size, negative cases for HTTP method and empty datasets, and edge cases for partial current-day data and response format.

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

- **ASSUM-001**: The response includes exactly 7 data points, one for each of the last 7 days. Basis: Inferred from 'last 7 days' in request; no explicit count or window definition in input.
- **ASSUM-002**: The current day is included in the seven-day window even if incomplete. Basis: Open question in input: 'Should the endpoint include the current day if it is incomplete?'.
- **ASSUM-003**: The response body is a JSON array of objects. Basis: Open question in input: 'What is the expected response format?'.

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)

## Verifier routing (proposed)

- "A request for daily user creation counts returns exactly seven days ordered oldest first" → hurl
- "The response contains exactly seven days of data" → hurl
- "The response does not include data older than seven days" → hurl
- "A POST request to the endpoint is rejected" → hurl
- "The response returns zero counts for all days when no users were created" → hurl
- "The response includes the current day even if it is incomplete" → hurl
- "The response body is formatted as a JSON array" → hurl