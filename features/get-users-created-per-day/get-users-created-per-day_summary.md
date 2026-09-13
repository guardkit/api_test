# Feature Spec Summary: Get Users Created Per Day

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 7 total (1 smoke, 0 regression)
**Assumptions**: 4 total (0 high / 0 medium / 4 low confidence)
**Review required**: Yes

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)

## Scope

This specification covers the GET /users/created-per-day endpoint which returns the number of users created on each of the last 7 days, ordered oldest first. It includes happy-path validation, boundary checks for date ranges, negative cases for method and authentication, and edge cases for empty data sets.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 1 |
| Boundary conditions (@boundary) | 2 |
| Negative cases (@negative) | 2 |
| Edge cases (@edge-case) | 2 |

## Deferred Items

None.

## Open Assumptions (low confidence)

- **ASSUM-001**: The response includes exactly 7 data points for the preceding week. Basis: Inferred from request description; not explicitly stated in input.
- **ASSUM-002**: The oldest day in the response is exactly 7 days before the current day. Basis: Inferred from 'last 7 days' phrasing; could mean 6 days ago or include today.
- **ASSUM-003**: The newest day in the response is yesterday, not today. Basis: Inferred from 'last 7 days' phrasing; could include today.
- **ASSUM-004**: The endpoint requires authentication. Basis: Not stated in input; common security practice for analytics endpoints.

## Verifier routing (proposed)

- "A request to the endpoint returns exactly seven days of data ordered oldest first" → hurl
- "The oldest day in the response is exactly seven days ago" → hurl
- "The newest day in the response is yesterday" → hurl
- "A POST request to the endpoint is rejected" → hurl
- "A request without authentication is rejected" → hurl
- "The endpoint returns zero counts for all days when no users were created" → hurl
- "The endpoint returns zero counts for all days when the user table is empty" → hurl

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "Get Users Created Per Day" --context features/get-users-created-per-day/get-users-created-per-day_summary.md