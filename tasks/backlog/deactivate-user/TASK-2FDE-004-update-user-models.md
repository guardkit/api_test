---
id: TASK-2FDE-004
title: Update user models
task_type: declarative
parent_review: TASK-REV-2FDE
feature_id: FEAT-2FDE
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
---

Update the user model to support deactivation.

## The words of the request this task serves

> Add a PATCH /users/{user_id}/deactivate endpoint that sets the user inactive and returns the updated user, with 404 for an unknown id and 409 if already inactive.

## Files to Create

- `src/users/schemas.py` (if not existing)

## Files to Modify

- `src/users/models.py`
- `src/users/schemas.py`

## Acceptance Criteria

- User model has is_active field
- User schema includes is_active field
- All modified files pass lint/format checks with zero errors

## Implementation Notes

- Add is_active boolean to User model
- Update Pydantic schemas to include is_active
- Ensure migrations are generated