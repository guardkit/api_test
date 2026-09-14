# Feature Spec Summary: User Creation Daily Counts

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 6 total (1 smoke, 0 regression)
**Assumptions**: 3 total (0 high / 0 medium / 3 low confidence)
**Review required**: Yes

## Scope

This specification covers the GET /users/created-per-day endpoint which returns the number of users created on each of the last 7 days, ordered oldest to newest. The input was sparse on response format, handling of incomplete current-day data, and explicit method restrictions, so low-confidence assumptions are surfaced for review.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 1 |
| Boundary conditions (@boundary) | 2 |
| Negative cases (@negative) | 3 |
| Edge cases (@edge-case) | 1 |

## Deferred Items

None.

## Open Assumptions (low confidence)

- **ASSUM-001**: The response includes the current day as the most recent entry. Basis: Inferred from 'last 7 days' phrasing; the input does not specify whether the current day is included or if only full days are returned.
- **ASSUM-002**: The endpoint returns exactly seven data points regardless of how many days have actual user creations. Basis: The input states 'must return exactly 7 data points' but does not clarify how to handle days with zero creations; assumed to include zero-count days.
- **ASSUM-003**: The endpoint only accepts GET requests and rejects all other HTTP methods. Basis: The input specifies a GET endpoint but does not explicitly list other methods; assumed to follow standard REST conventions.

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)

## Verifier routing (proposed)

- "A request for daily user creation counts returns exactly seven days ordered oldest first" → hurl
- "The response contains exactly seven days of data" → hurl
- "The response does not contain fewer than seven days of data" → hurl
- "The response succeeds even when no users were created in the last 7 days" → hurl
- "A POST request to the endpoint is rejected" → hurl
- "The endpoint fails gracefully when the user database is unavailable" → hurl

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "User Creation Daily Counts" --context features/created-per-day/created-per-day_summary.md