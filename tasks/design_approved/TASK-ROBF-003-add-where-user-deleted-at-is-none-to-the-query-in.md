---
autobuild_state:
  base_branch: fix/TASK-FEAT39F6FIX1-10141815
  current_turn: 0
  last_updated: '2026-09-10T14:40:36.099604'
  max_turns: 3
  started_at: '2026-09-10T14:40:36.099600'
  turns: []
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/api_test/.forge/worktrees/build-FEAT-39F6-20260910141815
complexity: 5
conductor_workspace: null
created: 2025-12-04 00:00:00+00:00
dependencies: []
id: TASK-ROBF-003
implementation_mode: task-work
parallel_group: 2
parent_review: TASK-FEAT39F6FIX1
priority: medium
status: design_approved
tags:
- repair-of-build-feat-39f6-20260907055525-attempt11
task_type: feature
title: Add `.where(User.deleted_at.is_(None))` to the query in `src/users/crud.py`
  `get_user_by_email()` (line 100) so deleted users are excluded, matching the filter
  used in `get_user()` and `get_users()`.
updated: 2025-12-04 00:00:00+00:00
---

# Add `.where(User.deleted_at.is_(None))` to the query in `src/users/crud.py` `get_user_by_email()` (line 100) so deleted users are excluded, matching the filter used in `get_user()` and `get_users()`.

## Description

Add `.where(User.deleted_at.is_(None))` to the query in `src/users/crud.py` `get_user_by_email()` (line 100) so deleted users are excluded, matching the filter used in `get_user()` and `get_users()`.

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