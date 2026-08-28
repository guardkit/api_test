# Feature Spec Summary: Add min_count query parameter to GET /users/count-by-domain

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 8 total (1 smoke, 0 regression)
**Assumptions**: 3 total (0 high / 0 medium / 3 low confidence)
**Review required**: Yes

## Scope

This specification covers the addition of an optional `min_count` query parameter to the `GET /users/count-by-domain` endpoint. It defines happy-path filtering, backward compatibility when the parameter is omitted, boundary conditions for valid and invalid values, and negative cases for malformed input.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 2 |
| Boundary conditions (@boundary) | 3 |
| Negative cases (@negative) | 4 |
| Edge cases (@edge-case) | 1 |

## Deferred Items

None.

## Open Assumptions (low confidence)

- **ASSUM-001**: The endpoint returns a JSON object mapping domain names to user counts. Basis: Inferred from problem statement; exact response structure not confirmed.
- **ASSUM-002**: Negative min_count values are rejected with a bad request response. Basis: Open question in input: 'Should the endpoint return a 400 Bad Request for negative min_count values or silently ignore them?'
- **ASSUM-003**: The maximum allowable min_count is 10,000. Basis: Open question in input: 'What is the maximum allowable value for min_count to prevent performance degradation?'

## Verifier routing (proposed)

- "Providing a valid min_count filters domains below that count" → hurl
- "Omitting the min_count parameter returns all domains" → hurl
- "A minimum count of zero includes all domains" → hurl
- "A negative minimum count is rejected" → hurl
- "A minimum count exceeding the maximum allowed value is rejected" → hurl
- "A non-integer minimum count is rejected" → hurl
- "An empty minimum count value is rejected" → hurl
- "A minimum count higher than any existing domain count returns no domains" → hurl

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)