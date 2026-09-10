# Feature: Repair of build-FEAT-39F6-20260907055525-attempt11

## Overview

This feature addresses improvements identified in the TASK-FEAT39F6FIX1 review.

**Parent Review**: [TASK-FEAT39F6FIX1](../TASK-FEAT39F6FIX1.md)
**Review Report**: [TASK-FEAT39F6FIX1-review-report.md](/home/richardwoollcott/Projects/appmilla_github/api_test/.forge/worktrees/build-FEAT-39F6-20260910141815/.claude/reviews/TASK-FEAT39F6FIX1-review-report.md)

## Problem Statement

Problem statement to be extracted from review findings.

## Solution

1. Add `timezone=True` to the `deleted_at` column in `src/users/models.py` (line 66: change `DateTime` to `DateTime(timezone=True)`) and update the Alembic migration `alembic/versions/39f6_add_deleted_at_column_to_users.py` (line 35: change `sa.DateTime()` to `sa.DateTime(timezone=True)`) so PostgreSQL stores `TIMESTAMP WITH TIME ZONE` and accepts the timezone-aware `datetime.now(UTC)` values written by `crud.delete_user()`.
2. Add try/except around `db.flush()` and `await db.commit()` in `src/users/crud.py` `delete_user()` (lines 161–163) to catch `SQLAlchemyError`, log it, and either retry or return a meaningful error — matching the error-handling pattern used in `create_user()` (lines 38–45).
3. Add `.where(User.deleted_at.is_(None))` to the query in `src/users/crud.py` `get_user_by_email()` (line 100) so deleted users are excluded, matching the filter used in `get_user()` and `get_users()`.
4. Correct the task description in `TASK-FEAT39F6FIX1-repair.md` to reference `DELETE /users/by-email` instead of `DELETE /users/{id}` to accurately reflect the failing endpoint.

## Scope

### In Scope
- To be defined based on review recommendations

### Out of Scope
- To be defined based on review analysis

## Success Criteria

Success criteria to be defined based on review findings.

## Subtasks

| ID | Title | Method | Status |
|----|-------|--------|--------|
| TASK-ROBF-001 | Add `timezone=True` to the `deleted_at` column in `src/users/models.py` (line 66: change `DateTime` to `DateTime(timezone=True)`) and update the Alembic migration `alembic/versions/39f6_add_deleted_at_column_to_users.py` (line 35: change `sa.DateTime()` to `sa.DateTime(timezone=True)`) so PostgreSQL stores `TIMESTAMP WITH TIME ZONE` and accepts the timezone-aware `datetime.now(UTC)` values written by `crud.delete_user()`. | task-work | backlog |
| TASK-ROBF-002 | Add try/except around `db.flush()` and `await db.commit()` in `src/users/crud.py` `delete_user()` (lines 161–163) to catch `SQLAlchemyError`, log it, and either retry or return a meaningful error — matching the error-handling pattern used in `create_user()` (lines 38–45). | task-work | backlog |
| TASK-ROBF-003 | Add `.where(User.deleted_at.is_(None))` to the query in `src/users/crud.py` `get_user_by_email()` (line 100) so deleted users are excluded, matching the filter used in `get_user()` and `get_users()`. | task-work | backlog |
| TASK-ROBF-004 | Correct the task description in `TASK-FEAT39F6FIX1-repair.md` to reference `DELETE /users/by-email` instead of `DELETE /users/{id}` to accurately reflect the failing endpoint. | task-work | backlog |


## Related Documents

- Review report (linked above)
- Parent review task [TASK-FEAT39F6FIX1](../TASK-FEAT39F6FIX1.md)
