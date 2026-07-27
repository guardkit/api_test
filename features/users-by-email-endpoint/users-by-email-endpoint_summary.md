# User Lookup By Email — one-minute summary

**What:** `GET /users/by-email?email=<address>` → 200 with that user's public record,
404 when no user has the address, 422 on a malformed address, 503 naming the database
when it is down (the convention `/users/count` established). Declared before the
by-id route so neither shadows the other. Read-only, no auth (the repo's posture).

**Why this feature for the third e2e run:** the third run is the CLEAN-ROUTINE-DATUM
candidate — every fix from the last three days is deployed, so the chain is under
test, not the Player. The feature is deliberately thin: the query already exists
(`crud.get_user_by_email`, shipped for the create path's duplicate check); the factory
adds routing, validation, and found/not-found semantics. One honest rung over
`/users/count`: a parameterized read with a real 422 and a real 404.

**Scope:** one route + tests. No new query, no new schema (reuses `UserPublic`),
no pagination, no auth.

**Open for Rich's review:** the four assumptions in
`users-by-email-endpoint_assumptions.yaml` — ASSUM-002 (exact-match, no
case-normalization) is the one worth a hard look. All marked `pending`.
