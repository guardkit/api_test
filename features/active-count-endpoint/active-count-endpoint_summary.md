# Feature Spec Summary: Active Count Endpoint

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 4 total (1 smoke, 0 regression)
**Assumptions**: 2 total (0 high / 0 medium / 2 low confidence)
**Review required**: Yes

## Scope

This specification covers the GET /users/active-count endpoint which returns the number of active and inactive users as separate integer counts. The input was sparse on exact response field names and empty-set behaviour, so low-confidence assumptions are surfaced for review.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 1 |
| Boundary conditions (@boundary) | 1 |
| Negative cases (@negative) | 2 |
| Edge cases (@edge-case) | 0 |

## Deferred Items

None.

## Open Assumptions (low confidence)

- **ASSUM-001**: The endpoint returns a JSON response with active_count and inactive_count fields. Basis: Inferred from request description; exact field names not specified in input.
- **ASSUM-002**: The endpoint returns 0 for both counts when no users exist. Basis: Inferred from request description; behaviour for empty user set not stated.

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)

## Verifier routing (proposed)

- "A request to the active count endpoint returns both counts" → hurl
- "The endpoint returns zero for both counts when no users exist" → hurl
- "A POST request to the active count endpoint is rejected" → hurl
- "A request to an invalid path on the user statistics service is rejected" → hurl

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "Active Count Endpoint" --context features/active-count-endpoint/active-count-endpoint_summary.md