# Feature Spec Summary: Get Users Created Per Day

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 8 total (1 smoke, 0 regression)
**Assumptions**: 3 total (0 high / 0 medium / 3 low confidence)
**Review required**: Yes

## Scope

This specification covers the GET /users/created-per-day endpoint which returns the number of users created on each of the last 7 days, ordered oldest first. The input was sparse on authentication policy, zero-count day handling, and exact response format, so these are captured as low-confidence assumptions.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 1 |
| Boundary conditions (@boundary) | 4 |
| Negative cases (@negative) | 3 |
| Edge cases (@edge-case) | 1 |

## Deferred Items

None.

## Open Assumptions (low confidence)

- **ASSUM-001**: The response includes exactly 7 data points covering the most recent 7-day window. Basis: Inferred from feature description; not explicitly stated in input.
- **ASSUM-002**: The endpoint requires authentication. Basis: Open question in input; no authentication policy provided.
- **ASSUM-003**: Days with no new users are reported with a count of zero. Basis: Open question in input; no policy on zero-count days.

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)

## Verifier routing (proposed)

- "A successful request returns exactly seven days of data ordered oldest first" → hurl
- "The response contains exactly seven data points" → hurl
- "The response does not contain fewer than seven data points" → hurl
- "A POST request to the endpoint is rejected" → hurl
- "An unauthenticated request is rejected" → hurl
- "Days with no new users are reported with a count of zero" → hurl
- "The oldest day in the response is exactly six days before today" → hurl
- "The newest day in the response is today" → hurl

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "Get Users Created Per Day" --context features/get-users-created-per-day/get-users-created-per-day_summary.md