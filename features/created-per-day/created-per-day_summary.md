# Feature Spec Summary: User Creation Metrics

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 8 total (1 smoke, 0 regression)
**Assumptions**: 3 total (0 high / 0 medium / 3 low confidence)
**Review required**: Yes

## Scope

This specification covers the GET /users/created-per-day endpoint which returns a time-series of user creation counts for the most recent 7-day window. It defines happy-path, boundary, negative, and edge-case behaviours. The input was sparse on authentication requirements, window definition, and exact response shape, so low-confidence assumptions are surfaced for review.

## Assumption Resolution

| ID | Assumption | Confidence | Basis |
|----|-------------|------------|-------|
| ASSUM-001 | The 7-day window includes the current day | low | Not stated in input; could be last 7 completed days or last 7 including today |
| ASSUM-002 | The endpoint requires authentication | low | Not stated in input; could be public or require auth |
| ASSUM-003 | The response must return exactly 7 data points | low | Input says 'last 7 days' but does not explicitly mandate exactly 7 points if data is sparse |

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 1 |
| Boundary conditions (@boundary) | 2 |
| Negative cases (@negative) | 3 |
| Edge cases (@edge-case) | 2 |

## Deferred Items

None.

## Verifier routing (proposed)

- "Requesting the metrics returns exactly seven days ordered oldest first" → hurl
- "The response includes the current day as the newest entry" → hurl
- "The response does not include dates older than seven days ago" → hurl
- "A POST request to the endpoint is rejected" → hurl
- "An unauthenticated request is rejected" → hurl
- "The response returns zero counts when no users were created" → hurl
- "The response includes days with zero creations" → hurl
- "The endpoint handles service unavailability gracefully" → hurl

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "User Creation Metrics" --context features/created-per-day/created-per-day_summary.md