---
complexity: 4
dependencies:
- TASK-651C-001
feature_id: FEAT-651C
id: TASK-651C-002
implementation_mode: task-work
parent_review: TASK-REV-651C
status: design_approved
task_type: feature
title: Implement active count query
wave: 2
---

Implement the database query to count active and inactive users.

## The words of the request this task serves

> Add a GET /users/active-count endpoint that returns the number of active and inactive users as separate counts.

## Files to Create

- `src/users/crud.py` (if not existing, or append to it)

## Files to Modify

- `src/users/crud.py`

## Acceptance Criteria

- `get_active_user_counts()` returns a dictionary or model with `active_count` and `inactive_count`
- Query correctly filters by `is_active` flag
- Query handles empty user set correctly (returns 0 for both)
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

Use SQLAlchemy 2.0 `select()` and `func.count()` patterns. Ensure the query is async.