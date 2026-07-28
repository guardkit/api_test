# users-delete-by-email — proposal summary (for Rich's one-minute read)

**What:** `DELETE /users/by-email?email=<address>` — remove an account by email
without first looking up its id. 204 empty on success · 404 unknown (and on the
second delete of the same email) · 422 malformed before the DB · 503 naming the
database when it is down.

**Why thin:** pure reuse of two shipped seams (`crud.get_user_by_email` +
`crud.delete_user`); route/response semantics only. The realism rung: a
DESTRUCTIVE op whose pass-bar demands the round-trip (delete → lookup must 404)
— actual deletion cannot be faked by a hardcoded response.

**Inherited conventions (not new assumptions):** EmailStr 422-before-DB · the
404 detail shape · the /users/count 503 convention · route order (literal before
parameterized — now in the DELETE group, the class that bit twice).

**The 4 assumptions awaiting your read** (`_assumptions.yaml`): 204-empty
mirror of by-id delete · exact-match email (no normalization) · second delete =
404 not idempotent-204 (**ASSUM-003 is the one worth your hard look**) · hard
delete, no auth.

**Factory first:** this task carries the first `conformance:` block (FEAT-SCG
machinery) — modest textual rules; the run's receipt is the point.
