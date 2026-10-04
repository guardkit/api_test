---
complexity: 5
dependencies: []
feature_id: FEAT-2FDE
id: TASK-2FDE-001
implementation_mode: task-work
parent_review: TASK-REV-2FDE
status: design_approved
task_type: feature
title: Create deactivation endpoint
wave: 1
---

Implement the PATCH /users/{user_id}/deactivate endpoint.

## The words of the request this task serves

> Add a PATCH /users/{user_id}/deactivate endpoint that sets the user inactive and returns the updated user, with 404 for an unknown id and 409 if already inactive.

## Files to Create

- `src/users/router.py` (if not existing)

## Files to Modify

- `src/users/router.py`

## Acceptance Criteria

- PATCH /users/{user_id}/deactivate returns 200 with updated user when active
- PATCH /users/{user_id}/deactivate returns 404 when user not found
- PATCH /users/{user_id}/deactivate returns 409 when user already inactive
- Endpoint is documented in API docs

## Implementation Notes

- Use FastAPI router
- Ensure the endpoint is wired into the main app
- The route should be protected by authentication (assume existing auth middleware)