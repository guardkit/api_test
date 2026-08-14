# Hurl-Twin Graduation Ledger (Q4)

The graduation ledger Rich's options-card Q4 asks for: every twin's life events
in one place, so a twin's earned trust is auditable — authored against an
approved scenario, each red it catches, each fix re-verified, and any human
adjudication. A twin graduates on evidence, never on assertion.

Event vocabulary: `authored` | `red-caught` | `fix-verified` | `adjudication`.
Evidence refs cite live-gate envelope run_ids (qa/gates/history/<run_id>.json)
or commit shas.

| date | feature | twin | event | evidence ref |
|------|---------|------|-------|--------------|
| 2026-08-14 | time-endpoint (specs 6.1, 6.2) · uptime-endpoint (spec 2.2) · users-delete-by-email (specs 9.1, 9.4) | all five twins under qa/twins/ | authored | this commit; hurlfmt --check clean on all five; first full bench = run PILOT-HURL-local-20260814T205843Z |
| 2026-08-14 | time-endpoint (spec 6.1) | time-endpoint/reading-current-server-time.hurl | red-caught (seeded defect: /time service field "wrong-name") | envelope run PILOT-HURL-local-20260814T210024Z, verdict fail — failing assertion hurl-twins::reading-current-server-time::31 observed `actual: string <wrong-name>; expected: string <api_test>` |
| 2026-08-14 | time-endpoint (spec 6.1) | time-endpoint/reading-current-server-time.hurl | fix-verified (seeded defect reverted; defect never committed) | envelope run PILOT-HURL-local-20260814T210040Z, verdict pass, 21/21 assertions green |
| 2026-08-14 | users-delete-by-email (specs 9.1, 9.4) | users-delete-by-email/delete-existing-user.hurl + double-delete-honest-404.hurl | red-caught (REAL pre-existing defect, first bench run: `crud.delete_user` flushes but never commits, so over the wire DELETE /users/by-email returns 204 yet the row persists — lookup after delete is 200 not 404, second delete is 204 not 404; the in-process suite shares one session and could never see it) | envelope run PILOT-HURL-local-20260814T205843Z, verdict fail — hurl-twins::delete-existing-user::43 (actual 200, expected 404) and hurl-twins::double-delete-honest-404::38 (actual 204, expected 404) |
| 2026-08-14 | users-delete-by-email (specs 9.1, 9.4) | users-delete-by-email/* | fix-verified (one-line fix `await db.commit()` in src/users/crud.py delete_user, applied in the bench working tree ONLY — not committed, this pilot commit is path-limited to qa/) | envelope run PILOT-HURL-local-20260814T205940Z, verdict pass, 21/21 green |
| 2026-08-14 | users-delete-by-email | src/users/crud.py delete_user (and update_user, same missing-commit shape, untested by these twins) | adjudication PENDING → RULED same day, rows below | see PILOT-REPORT + the two envelope runs above |
| 2026-08-14 | users-delete-by-email + users-put | src/users/crud.py delete_user + update_user | adjudication (Rich ruled 08-14: the commit fix LANDS — delete_user's bench-verified one-liner committed, update_user gets the identical one-liner, and the update path gets its own persistence twin) | this commit |
| 2026-08-14 | users-put (no .feature exists; twin ordered by the 08-14 adjudication) | users-put/update-persists.hurl | authored (PUT then GET-back compare — the flush-without-commit defect class; hurlfmt --check clean) | this commit |
| 2026-08-14 | all six twins | qa/twins/** | fix-verified (both crud one-liners in the tree; full gate green through the real seam, 31/31 assertions — 21 prior + 10 from the new PUT twin) | envelope run LANE1-CRUD-local-20260814T222544Z, verdict pass |
