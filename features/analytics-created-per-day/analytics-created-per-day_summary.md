# Feature Spec Summary: User Creation Analytics - Created Per Day

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 4 total (1 smoke, 0 regression)
**Assumptions**: 3 total (0 high / 0 medium / 3 low confidence)
**Review required**: Yes

## Scope

This specification covers the `GET /users/created-per-day` endpoint which returns the number of users created on each of the last 7 days (today and the six preceding days), ordered from oldest to newest. The count includes both active and soft-deleted users. The endpoint accepts no query parameters and returns a JSON array of objects containing a date and a count.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 1 |
| Boundary conditions (@boundary) | 1 |
| Negative cases (@negative) | 1 |
| Edge cases (@edge-case) | 1 |

## Deferred Items

None.

## Open Assumptions (low confidence)

- **ASSUM-001**: The response includes exactly 7 entries, one for each of the last 7 days, ordered oldest to newest. Basis: Inferred from 'last 7 days' and 'oldest first' in request; exact count and ordering not explicitly confirmed.
- **ASSUM-002**: The response format is a JSON array of objects with "date" (ISO-8601) and "count" (integer) keys. Basis: Inferred from 'JSON array of objects' in request; exact key names and date format not confirmed.
- **ASSUM-003**: Soft-deleted users are indistinguishable from active users in the count. Basis: Inferred from 'counting soft-deleted users too' in request; exact storage mechanism not confirmed.

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)

## Verifier routing (proposed)

- "A successful request returns the last 7 days of creation counts" → hurl
- "The response includes exactly the last 7 days including today" → hurl
- "No users created in the last 7 days returns zero counts for each day" → hurl
- "All users created in the last 7 days are soft-deleted" → hurl

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "User Creation Analytics - Created Per Day" --context features/user-creation-analytics/created-per-day_summary.md