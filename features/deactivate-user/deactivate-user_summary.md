# Feature Spec Summary: Deactivate User Endpoint

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 6 total (1 smoke, 0 regression)
**Assumptions**: 3 total (0 high / 0 medium / 3 low confidence)
**Review required**: Yes

## Scope

This specification covers the PATCH /users/{user_id}/deactivate endpoint. It defines the happy-path deactivation of an active user, the 404 response for unknown IDs, the 409 response for already inactive users, and basic security/concurrency edge cases. The input was sparse on authentication requirements and the exact shape of the returned user object, so these are captured as low-confidence assumptions.

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

- **ASSUM-001**: The returned user object includes the updated status field. Basis: Inferred from the request statement 'returns the updated user'; exact shape not specified.
- **ASSUM-002**: The endpoint requires authentication. Basis: Not stated in the input; common security practice for user management endpoints.
- **ASSUM-003**: Concurrent requests to deactivate the same user are handled gracefully. Basis: Inferred from the edge-case category; exact concurrency model not specified.

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)

## Verifier routing (proposed)

- "Deactivating an active user succeeds" → hurl
- "Deactivating a non-existent user returns not found" → hurl
- "Deactivating an already inactive user returns conflict" → hurl
- "Deactivating a user without authentication is rejected" → hurl
- "Concurrent deactivation requests for the same user are handled gracefully" → toolchain
- "Deactivation fails gracefully when the user service is unavailable" → hurl