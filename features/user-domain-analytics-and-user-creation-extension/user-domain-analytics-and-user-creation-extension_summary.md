# Feature Spec Summary: User Domain Analytics and User Creation Extension

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 9 total (1 smoke, 0 regression)
**Assumptions**: 3 total (0 high / 0 medium / 3 low confidence)
**Review required**: Yes

## Scope

This specification covers the GET /users/count-by-domain endpoint on both freshly created and existing databases, and the POST /users endpoint on a freshly created database. It includes happy-path scenarios, boundary conditions for empty and single-domain responses, negative cases for missing fields and invalid filters, and edge cases for concurrency and duplicate email handling.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 3 |
| Boundary conditions (@boundary) | 2 |
| Negative cases (@negative) | 2 |
| Edge cases (@edge-case) | 2 |

## Deferred Items

None.

## Open Assumptions (low confidence)

- **ASSUM-001**: GET /users/count-by-domain returns an empty list when no users exist — basis: Inferred from problem statement; not explicitly stated whether empty list or 404 is expected
- **ASSUM-002**: POST /users requires a valid email address in the request body — basis: Inferred from domain context; not stated in input
- **ASSUM-003**: The response body for an empty domain count is an empty JSON array — basis: Inferred from problem statement; not explicitly stated whether empty list or 404 is expected

## Verifier routing (proposed)

- "Querying user domain counts on a fresh database returns an empty list" → hurl
- "Querying user domain counts on an existing database returns counts for each domain" → hurl
- "Creating a new user on a fresh database succeeds" → hurl
- "A fresh database returns an empty array for domain counts" → hurl
- "A database with exactly one domain returns a single count entry" → hurl
- "Creating a user without a required field fails" → hurl
- "Querying with an invalid domain filter returns an error" → hurl
- "Concurrent user creation on a fresh database handles race conditions" → hurl
- "Creating a user with a duplicate email on a fresh database fails" → hurl

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)