# Review Report — TASK-FEAT39F6FIX1

## Summary

Architectural review of the delete-by-email feature (FEAT-39F6) that fails 2 of 62 gate checks on Postgres: `delete-existing-user::40` and `double-delete-honest-404::35` both expect HTTP 204 but receive 503. The root cause is a timezone type mismatch: the `deleted_at` column is defined as `TIMESTAMP WITHOUT TIME ZONE` in both the Alembic migration and the SQLAlchemy model, but the code writes timezone-aware `datetime.now(UTC)` values. PostgreSQL rejects the write with a `SQLAlchemyError` (converted to 503), while SQLite accepts it silently. A secondary concern is the absence of database error handling in `crud.delete_user()`.

## Context Used

- task file: `/home/richardwoollcott/Projects/appmilla_github/api_test/.forge/worktrees/build-FEAT-39F6-20260910141815/tasks/backlog/add-deleted-at-column/TASK-FEAT39F6FIX1-repair.md`
- scope: `src/users/models.py`, `src/users/crud.py`, `src/users/router.py`, `src/users/exceptions.py`, `src/users/validators.py`, `src/users/schemas.py`, `src/db/session.py`, `src/db/base.py`, `src/main.py`, `alembic/versions/39f6_add_deleted_at_column_to_users.py`, `features/users-delete-by-email/users-delete-by-email.feature`, `features/users-delete-by-email/users-delete-by-email_assumptions.yaml`, `qa/twins/users-delete-by-email/delete-existing-user.hurl`, `qa/twins/users-delete-by-email/double-delete-honest-404.hurl`, `tests/acceptance/test_deleted_at_acceptance.py`
- clarification: defaults applied (unattended)
- fleet memory (MCP tier): DECLARED-ABSENT — no MCP in a headless harness run
- fleet memory (CLI tier): {"attempted": true, "ok": true, "exit_code": 0, "output": "\nSearch Results for 'Repair of build-FEAT-39F6-20260907055525-attempt11':\n\n1. [0.63] {\"approach\":\"guardkit autobuild player/coach \nloop\",\"domain_tags\":[\"task\"],\"duration_seconds\":240,\"id...\n", "stderr_tail": "INFO:httpx:HTTP Request: POST http://172.30.1.135:9000/v1/embeddings \"HTTP/1.1 200 OK\"\n"}

## Findings

### F1 — `deleted_at` column lacks timezone support; Postgres rejects timezone-aware writes

**Severity:** critical

**file:** `src/users/models.py`, lines 65–69; `alembic/versions/39f6_add_deleted_at_column_to_users.py`, line 35

**Evidence:** The migration creates the column as `sa.Column("deleted_at", sa.DateTime(), nullable=True)` — in PostgreSQL this maps to `TIMESTAMP WITHOUT TIME ZONE`. The model declares the same: `DateTime` without `timezone=True`. The `crud.delete_user()` function (line 160) writes `user.deleted_at = datetime.now(UTC)`, which produces a timezone-aware datetime. PostgreSQL rejects a timezone-aware value into a `WITHOUT TIME ZONE` column with a `DataError`/`ProgrammingError` (both subclasses of `SQLAlchemyError`), which bubbles up to the route handler and is returned as HTTP 503. SQLite is type-lenient and silently accepts the value.

The acceptance test at `tests/acceptance/test_deleted_at_acceptance.py:129` explicitly asserts `deleted_at.tzinfo is not None`, confirming the design intent was timezone-aware storage — but the column definition contradicts that intent.

**Why it is a defect:** This is a cross-database type incompatibility. The column definition must match the data the application writes. The code writes timezone-aware datetimes (`datetime.now(UTC)`); the column must accept them.

### F2 — `crud.delete_user()` has no database error handling

**Severity:** high

**file:** `src/users/crud.py`, lines 160–163

**Evidence:** The `delete_user()` function sets `user.deleted_at`, calls `db.add(user)`, `await db.flush()`, and `await db.commit()` — none of which are wrapped in try/except. If `flush()` or `commit()` raises any `SQLAlchemyError` (e.g., constraint violation, connection drop, type error), the exception propagates directly to the route handler. While the route handler (`delete_user_by_email` at `router.py:543-549`) does catch `SQLAlchemyError` and returns 503, the CRUD function itself has no defensive error handling. This means: (a) the function is not composable with callers that expect a boolean return rather than an exception, and (b) the error context is lost when the route handler re-wraps it.

Compare with `create_user()` at `crud.py:38-45`, which wraps its flush/commit in try/except and handles `IntegrityError` explicitly.

**Why it is a defect:** The inconsistency in error handling between `create_user` and `delete_user` indicates a gap. The `delete_user` function should either handle its own errors or at minimum document that it can raise `SQLAlchemyError`. Given that the acceptance criteria depend on this function working correctly on Postgres, the missing error handling compounds the F1 defect.

### F3 — `crud.get_user_by_email()` does not filter by `deleted_at`

**Severity:** medium

**file:** `src/users/crud.py`, lines 90–102

**Evidence:** The `get_user_by_email()` function executes `select(User).where(User.email == email)` — it does NOT include `.where(User.deleted_at.is_(None))`. By contrast, `get_user()` (line 58–64) and `get_users()` (line 80–87) both filter by `deleted_at.is_(None)`. This means `get_user_by_email` can return a user whose `deleted_at` is already set (i.e., a soft-deleted user).

The `delete_user_by_email` route handler (`router.py:520-556`) calls `crud.get_user_by_email()` first, then `crud.delete_user()`. If `get_user_by_email` returns an already-deleted user, `delete_user()` calls `get_user()` internally, which filters by `deleted_at.is_(None)` and returns `None`, causing the route to return 404 — a misleading response for a user that exists but is already deleted.

**Why it is a defect:** Inconsistent filtering across user lookup functions. The `deleted_at` filter is a core part of the soft-delete contract (confirmed by ASSUM-003 in the assumptions file: "the absence is reported honestly"). `get_user_by_email` should exclude soft-deleted users to match the contract.

### F4 — Task description misidentifies the failing endpoint

**Severity:** low

**file:** `tasks/backlog/add-deleted-at-column/TASK-FEAT39F6FIX1-repair.md`, line 3

**Evidence:** The task description states: "DELETE /users/{id} answered 503 where 204 was expected." However, the two failing hurl checks are:
- `delete-existing-user.hurl` line 40: `DELETE {{base_url}}/users/by-email?email=...`
- `double-delete-honest-404.hurl` line 35: `DELETE {{base_url}}/users/by-email?email=...`

These hit the `/users/by-email` endpoint, not `/users/{id}`. The two endpoints have different route handlers (`delete_user_by_email` vs `delete_user`), different auth requirements (no auth on by-email, auth required on by-id), and different error handling paths.

**Why it is a defect:** Misidentification of the failing endpoint could misdirect the fix effort. The actual bug is in the `delete_user_by_email` → `crud.get_user_by_email` → `crud.delete_user` chain, not in the `/users/{id}` path.

## Recommendations

1. Add `timezone=True` to the `deleted_at` column in `src/users/models.py` (line 66: change `DateTime` to `DateTime(timezone=True)`) and update the Alembic migration `alembic/versions/39f6_add_deleted_at_column_to_users.py` (line 35: change `sa.DateTime()` to `sa.DateTime(timezone=True)`) so PostgreSQL stores `TIMESTAMP WITH TIME ZONE` and accepts the timezone-aware `datetime.now(UTC)` values written by `crud.delete_user()`.
2. Add try/except around `db.flush()` and `await db.commit()` in `src/users/crud.py` `delete_user()` (lines 161–163) to catch `SQLAlchemyError`, log it, and either retry or return a meaningful error — matching the error-handling pattern used in `create_user()` (lines 38–45).
3. Add `.where(User.deleted_at.is_(None))` to the query in `src/users/crud.py` `get_user_by_email()` (line 100) so deleted users are excluded, matching the filter used in `get_user()` and `get_users()`.
4. Correct the task description in `TASK-FEAT39F6FIX1-repair.md` to reference `DELETE /users/by-email` instead of `DELETE /users/{id}` to accurately reflect the failing endpoint.

## Phases Not Run

| Checkpoint | Spec pin | Disposition | What that means here |
|---|---|---|---|
| Phase 0 — ad-hoc task creation from free text | `task-review.md:93-101` | **REFUSED** | The leg is **id-form only**. `--task-id` names a task file that must already exist on disk. If it does not, the leg exits 2 naming the id — it never invents a task from the description. This mirrors the command's own no-silent-fallback rule (`task-review.md:87-91`). |
| Phase 1.6 — clarification questioner (Context A) | `task-review-ext.md:573-641`, gating `:325-330` | **AUTO-ANSWERED** | `--defaults` semantics. You must NOT ask clarifying questions. Apply the most defensible reading of the task and record it. The report's **Context Used** section carries the mandatory line `clarification: defaults applied (unattended)`. |
| Phase 1.5 — fleet memory, **MCP tier** | `task-review-ext.md:662-794` (never-blocks `:826`) | **DECLARED-ABSENT** | There is no MCP server in a headless harness run. Do not attempt MCP memory calls. The report says so by name so no reader mistakes a missing memory pass for an empty one. |
| Phase 1.5 — fleet memory, **CLI tier** | `guardkit memory search` | **ATTEMPTED-AND-RECORDED** | The leg (not you) runs the CLI tier before invoking you and injects its outcome into your context below. Whatever it returned — hits, no hits, or a failure — is recorded verbatim in the receipt. |
| Phase 4.5 — knowledge capture (3-5 free-text questions) | `task-review-ext.md:893-1018` | **DECLARED-ABSENT** | Blocking human Q&A with no defensible default. It does not run and the report says so. |
| Phase 5 — `[A]ccept / [R]evise / [I]mplement / [C]ancel` | `task-review.md:146-154` | **RELOCATED, not stripped** | The unattended leg does not *decide*; it *produces*. Findings present → the leg takes the `[I]mplement` path (it calls the existing fix-task producer, `implement_orchestrator.handle_implement_option_sync`) and prints the generated fix-task paths. Findings absent → the `[A]ccept` path: an empty artefact section **plus an explicit clean line**. The human judgement moves up one level, to the pipeline's own review gate, which is already attended and already carries a `gate_decision`. |
