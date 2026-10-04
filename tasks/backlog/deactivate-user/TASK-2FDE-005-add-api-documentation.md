---
id: TASK-2FDE-005
title: Add API documentation
task_type: documentation
parent_review: TASK-REV-2FDE
feature_id: FEAT-2FDE
wave: 4
implementation_mode: direct
complexity: 2
dependencies:
  - TASK-2FDE-001
---

Document the new deactivation endpoint.

## The words of the request this task serves

> Add a PATCH /users/{user_id}/deactivate endpoint that sets the user inactive and returns the updated user, with 404 for an unknown id and 409 if already inactive.

## Files to Create

- `docs/api/deactivate-user.md`

## Files to Modify

- `docs/API.md`

## Acceptance Criteria

- API documentation includes deactivation endpoint
- All modified files pass lint/format checks with zero errors

## Implementation Notes

- Include request/response examples
- Document error codes (404, 409)