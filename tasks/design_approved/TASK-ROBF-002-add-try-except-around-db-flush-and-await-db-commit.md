---
autobuild_state:
  base_branch: fix/TASK-FEAT39F6FIX1-10141815
  current_turn: 0
  last_updated: '2026-09-10T14:31:44.703385'
  max_turns: 3
  started_at: '2026-09-10T14:31:44.703382'
  turns: []
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/api_test/.forge/worktrees/build-FEAT-39F6-20260910141815
complexity: 5
conductor_workspace: repair-of-build-feat-39f6-20260907055525-attempt11-wave1-2
created: 2025-12-04 00:00:00+00:00
dependencies: []
id: TASK-ROBF-002
implementation_mode: task-work
parallel_group: 1
parent_review: TASK-FEAT39F6FIX1
priority: medium
status: design_approved
tags:
- repair-of-build-feat-39f6-20260907055525-attempt11
task_type: feature
title: Add try/except around `db.flush()` and `await db.commit()` in `src/users/crud.py`
  `delete_user()` (lines 161–163) to catch `SQLAlchemyError`, log it, and either retry
  or return a meaningful error — matching the error-handling pattern used in `create_user()`
  (lines 38–45).
updated: 2025-12-04 00:00:00+00:00
---

# Add try/except around `db.flush()` and `await db.commit()` in `src/users/crud.py` `delete_user()` (lines 161–163) to catch `SQLAlchemyError`, log it, and either retry or return a meaningful error — matching the error-handling pattern used in `create_user()` (lines 38–45).

## Description

Add try/except around `db.flush()` and `await db.commit()` in `src/users/crud.py` `delete_user()` (lines 161–163) to catch `SQLAlchemyError`, log it, and either retry or return a meaningful error — matching the error-handling pattern used in `create_user()` (lines 38–45).

## Acceptance Criteria

- [ ] Implementation complete
- [ ] Tests passing
- [ ] Code reviewed
- [ ] Documentation updated
- [ ] AC-ANTISTUB-1: All primary deliverable functions contain meaningful implementation logic (no stubs, pass-only bodies, or TODOs)
- [ ] AC-ANTISTUB-2: At least one test exercises a primary function end-to-end without mocking its core logic

## Files to Modify

- `src/users/crud.py`

## Implementation Details

Execute with `/task-work {task_id}` for full quality gates (architecture review, tests, code review).

## Dependencies

No dependencies.

## Notes

Auto-generated from TASK-FEAT39F6FIX1 recommendations.