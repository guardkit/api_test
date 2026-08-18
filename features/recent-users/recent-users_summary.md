# Feature Spec Summary: Recent Users Endpoint

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 10 total (1 smoke, 0 regression)
**Assumptions**: 3 total (0 high / 0 medium / 3 low confidence)
**Review required**: Yes

**Review required**: Yes

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)

## Scope

This specification covers the `/recent-users` HTTP GET endpoint that retrieves a list of the most recently added users. It defines the core retrieval behaviour, newest-first ordering, optional limit parameter handling (including default, valid explicit, and invalid values), and the empty-store case.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 3 |
| Boundary conditions (@boundary) | 4 |
| Negative cases (@negative) | 3 |
| Edge cases (@edge-case) | 0 |

## Deferred Items

None.

## Open Assumptions (low confidence)

- **ASSUM-001**: The default limit is 10 users when the limit parameter is omitted
- **ASSUM-002**: The maximum allowed limit value is 100 users
- **ASSUM-003**: The response contains full user objects with standard fields

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "Recent Users Endpoint" --context features/recent-users/recent-users_summary.md

## Verifier routing (proposed)

- "Requesting recent users without a limit returns the default number of newest users" → hurl
- "Requesting recent users with a valid explicit limit returns that many newest users" → hurl
- "Requesting recent users at the maximum allowed limit returns that many users" → hurl
- "Requesting recent users with a limit exceeding the maximum is rejected" → hurl
- "Requesting recent users with a limit of 1 returns a single newest user" → hurl
- "Requesting recent users with a limit of zero is rejected" → hurl
- "Requesting recent users with a negative limit is rejected" → hurl
- "Requesting recent users with a non-integer limit is rejected" → hurl
- "Requesting recent users from an empty store returns an empty list" → hurl
