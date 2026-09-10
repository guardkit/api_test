---
autobuild_state:
  base_branch: fix/TASK-FEAT39F6FIX1-10141815
  current_turn: 0
  last_updated: '2026-09-10T14:25:10.816111'
  max_turns: 3
  started_at: '2026-09-10T14:25:10.816105'
  turns: []
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/api_test/.forge/worktrees/build-FEAT-39F6-20260910141815
complexity: 5
conductor_workspace: repair-of-build-feat-39f6-20260907055525-attempt11-wave1-1
created: 2025-12-04 00:00:00+00:00
dependencies: []
id: TASK-ROBF-001
implementation_mode: task-work
parallel_group: 1
parent_review: TASK-FEAT39F6FIX1
priority: medium
status: design_approved
tags:
- repair-of-build-feat-39f6-20260907055525-attempt11
task_type: refactor
title: 'Add `timezone=True` to the `deleted_at` column in `src/users/models.py` (line
  66: change `DateTime` to `DateTime(timezone=True)`) and update the Alembic migration
  `alembic/versions/39f6_add_deleted_at_column_to_users.py` (line 35: change `sa.DateTime()`
  to `sa.DateTime(timezone=True)`) so PostgreSQL stores `TIMESTAMP WITH TIME ZONE`
  and accepts the timezone-aware `datetime.now(UTC)` values written by `crud.delete_user()`.'
updated: 2025-12-04 00:00:00+00:00
---

# Add `timezone=True` to the `deleted_at` column in `src/users/models.py` (line 66: change `DateTime` to `DateTime(timezone=True)`) and update the Alembic migration `alembic/versions/39f6_add_deleted_at_column_to_users.py` (line 35: change `sa.DateTime()` to `sa.DateTime(timezone=True)`) so PostgreSQL stores `TIMESTAMP WITH TIME ZONE` and accepts the timezone-aware `datetime.now(UTC)` values written by `crud.delete_user()`.

## Description

Add `timezone=True` to the `deleted_at` column in `src/users/models.py` (line 66: change `DateTime` to `DateTime(timezone=True)`) and update the Alembic migration `alembic/versions/39f6_add_deleted_at_column_to_users.py` (line 35: change `sa.DateTime()` to `sa.DateTime(timezone=True)`) so PostgreSQL stores `TIMESTAMP WITH TIME ZONE` and accepts the timezone-aware `datetime.now(UTC)` values written by `crud.delete_user()`.

## Acceptance Criteria

- [ ] Implementation complete
- [ ] Tests passing
- [ ] Code reviewed
- [ ] Documentation updated
- [ ] AC-ANTISTUB-1: All primary deliverable functions contain meaningful implementation logic (no stubs, pass-only bodies, or TODOs)
- [ ] AC-ANTISTUB-2: At least one test exercises a primary function end-to-end without mocking its core logic

## Files to Modify

- `src/users/models.py`
- `alembic/versions/39f6_add_deleted_at_column_to_users.py`

## Implementation Details

Execute with `/task-work {task_id}` for full quality gates (architecture review, tests, code review).

## Dependencies

No dependencies.

## Notes

Auto-generated from TASK-FEAT39F6FIX1 recommendations.