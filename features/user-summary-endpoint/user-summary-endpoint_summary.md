# Feature Spec Summary: User Summary Endpoint

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 6 total (1 smoke, 0 regression)
**Assumptions**: 3 total (0 high / 0 medium / 3 low confidence)
**Review required**: Yes

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)

## Scope

This specification covers the GET /users/{user_id}/summary endpoint for the api_test service. It defines the behaviour for retrieving a user's public record enriched with derived fields (days since creation and active status), handling unknown user IDs with a not found response, and managing database unavailability through cache fallback or explicit error naming.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 1 |
| Boundary conditions (@boundary) | 2 |
| Negative cases (@negative) | 2 |
| Edge cases (@edge-case) | 2 |

## Deferred Items

None

## Open Assumptions (low confidence)

- ASSUM-001: The 'public record' consists of username, display name, and profile metadata fields
- ASSUM-002: The 'active' status is a stored boolean field in the user record
- ASSUM-003: The 'days since created' is calculated as the integer number of days between the user's creation date and the current server date

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "User Summary Endpoint" --context features/user-summary-endpoint/user-summary-endpoint_summary.md
