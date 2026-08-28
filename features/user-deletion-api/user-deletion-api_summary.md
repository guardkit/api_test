# Feature Spec Summary: User Deletion API

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 4 total (1 smoke, 0 regression)
**Assumptions**: 3 total (0 high / 0 medium / 3 low confidence)
**Review required**: Yes

## Scope

This specification covers the DELETE /users/{user_id} endpoint and the requirement that deleted users are excluded from all count endpoints in real time. It defines the happy-path deletion, handling of unknown IDs, idempotency for already-deleted users, and real-time count reflection.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 1 |
| Boundary conditions (@boundary) | 1 |
| Negative cases (@negative) | 2 |
| Edge cases (@edge-case) | 1 |

## Deferred Items

None.

## Open Assumptions (low confidence)

None. All assumptions are medium or high confidence; however, because no assumptions were confirmed, the review flag is set.

## Verifier routing (proposed)

- "Deleting an existing user succeeds" → hurl
- "Deleting a non-existent user returns not found" → hurl
- "Deleting an already deleted user returns not found" → hurl
- "Deletion is reflected in real time across all count endpoints" → hurl

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)