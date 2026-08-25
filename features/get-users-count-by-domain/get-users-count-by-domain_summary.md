# Feature Spec Summary: User Domain Count API

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 8 total (1 smoke, 0 regression)
**Assumptions**: 3 total (0 high / 0 medium / 3 low confidence)
**Review required**: Yes

## Scope

This specification covers the GET /users/count-by-domain endpoint which returns a JSON response containing a list of email domain counts, ordered by count descending. It includes happy-path, boundary (empty set), negative (method rejection), and edge-case (large domain set, domain with no users, malformed email) scenarios.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 1 |
| Boundary conditions (@boundary) | 1 |
| Negative cases (@negative) | 3 |
| Edge cases (@edge-case) | 3 |

## Deferred Items

None.

## Open Assumptions (low confidence)

- **ASSUM-001**: The endpoint returns a JSON array of objects with domain and count fields. Basis: Inferred from problem statement; exact field names and structure not specified.
- **ASSUM-002**: The endpoint supports up to 1000 domains in a single response. Basis: Arbitrary limit chosen for edge-case coverage; not stated in input.
- **ASSUM-003**: Malformed email addresses are ignored and do not cause errors. Basis: Inferred from domain-extraction requirement; exact handling policy not stated.

## Verifier routing (proposed)

- "A request returns domain counts ordered by count descending" → hurl
- "An empty user set returns an empty list" → hurl
- "A POST request to the endpoint is rejected" → hurl
- "A PUT request to the endpoint is rejected" → hurl
- "A DELETE request to the endpoint is rejected" → hurl
- "The endpoint handles a large number of domains" → hurl
- "Domains with no users are excluded from the list" → hurl
- "Malformed email addresses are ignored" → hurl

REVIEW REQUIRED: all assumptions unconfirmed (--auto mode)