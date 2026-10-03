---
id: TASK-651C-001
title: Create active count schema
task_type: declarative
parent_review: TASK-REV-651C
feature_id: FEAT-651C
wave: 1
implementation_mode: direct
complexity: 2
dependencies: []
---

Create the Pydantic schema for the active count response.

## The words of the request this task serves

> Add a GET /users/active-count endpoint that returns the number of active and inactive users as separate counts.

## Files to Create

- `src/users/schemas.py` (if not existing, or append to it)

## Files to Modify

- `src/users/schemas.py`

## Acceptance Criteria

- `ActiveCountResponse` schema contains `active_count` and `inactive_count` as non-negative integers
- Schema is accessible from `src/users/schemas.py`
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

This is a declarative task. The schema should be a simple Pydantic model.