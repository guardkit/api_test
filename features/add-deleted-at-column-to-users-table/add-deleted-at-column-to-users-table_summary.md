# Feature Spec Summary: Add deleted_at column to users table

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 5 total (1 smoke, 0 regression)
**Assumptions**: 2 total (0 high / 0 medium / 2 low confidence)
**Review required**: Yes

## Scope

This specification covers the addition of a nullable `deleted_at` timestamp column to the `users` table. The primary goal is to unblock the `POST /users` and `GET /users/count-by-domain` endpoints which currently fail due to the missing column. The spec defines the column's existence, nullability, type, and basic query behaviour.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 1 |
| Boundary conditions (@boundary) | 2 |
| Negative cases (@negative) | 2 |
| Edge cases (@edge-case) | 0 |

## Deferred Items

None.

## Open Assumptions (low confidence)

- **ASSUM-001**: The `deleted_at` column must be a nullable timestamp. Basis: Inferred from problem statement; exact database type and nullability not explicitly stated.
- **ASSUM-002**: The database supports nullable timestamp columns. Basis: Inferred from problem statement; database engine not specified.

## Verifier routing (proposed)

- "The deleted_at column exists and is nullable" → hurl
- "A user record can have a null deleted_at value" → hurl
- "A user record can have a non-null deleted_at value" → hurl
- "The deleted_at column does not require a value" → hurl
- "The deleted_at column is not a boolean type" → hurl

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)