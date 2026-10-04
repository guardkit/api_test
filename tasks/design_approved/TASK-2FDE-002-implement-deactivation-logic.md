---
complexity: 5
dependencies:
- TASK-2FDE-001
feature_id: FEAT-2FDE
id: TASK-2FDE-002
implementation_mode: task-work
parent_review: TASK-REV-2FDE
status: design_approved
task_type: feature
title: Implement deactivation logic
wave: 2
---

Implement the deactivation logic in the CRUD layer.

## The words of the request this task serves

> Add a PATCH /users/{user_id}/deactivate endpoint that sets the user inactive and returns the updated user, with 404 for an unknown id and 409 if already inactive.

## Files to Create

- `src/users/crud.py` (if not existing)

## Files to Modify

- `src/users/crud.py`

## Acceptance Criteria

- Deactivation logic correctly updates user status
- Returns 404 when user does not exist
- Returns 409 when user is already inactive
- Logic is atomic and handles concurrency

## Implementation Notes

- Use SQLAlchemy async session
- Implement as a repository pattern method
- Ensure the operation is idempotent for the same user