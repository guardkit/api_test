# Users Count Endpoint — one-minute summary

**What:** `GET /users/count` → `{"count": <non-negative integer>}`. Read-only, no auth
(the repo's standing posture), declared inside the existing users router BEFORE the
by-id route so neither shadows the other.

**Why this feature for the second e2e run:** FEAT-UPT1 proved the chain on a
dependency-free endpoint. This one is the next honest step: still single-task and
small, but **data-bearing** — the count comes from the real users table, so the
mandatory `dependency_down_degradation` negative path means something (DB down →
503 naming the cause, never a raw 500 or an invented number), and the
seeded-data round-trip (create a user → count increments) is exactly the shape a
hardcoded stub cannot fake.

**Scope:** one route + one response schema + tests. No new package (extends
`src/users/router.py`); one small edit surface. No pagination, no filters, no auth.

**Open for Rich's review:** the four assumptions in
`users-count-endpoint_assumptions.yaml` — chiefly the 503-on-DB-down convention
(ASSUM-001) and the hard-delete count semantics (ASSUM-002). All marked `pending`;
nothing is confirmed until his word.
