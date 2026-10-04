---
id: TASK-2FDE-003
title: Add deactivation tests
task_type: testing
parent_review: TASK-REV-2FDE
feature_id: FEAT-2FDE
wave: 3
implementation_mode: direct
complexity: 3
dependencies:
  - TASK-2FDE-002
---

Add tests for the deactivation endpoint.

## The words of the request this task serves

> Add a PATCH /users/{user_id}/deactivate endpoint that sets the user inactive and returns the updated user, with 404 for an unknown id and 409 if already inactive.

## Files to Create

- `tests/users/test_deactivate.py`

## Files to Modify

- `tests/users/__init__.py`

## Acceptance Criteria

- Test happy path: active user becomes inactive
- Test 404: unknown user ID
- Test 409: already inactive user
- Test concurrency: two simultaneous requests
- Test service unavailable (mocked)

## Implementation Notes

- Use pytest with httpx for async requests
- Use the existing test fixtures
- Include a seam test for the database boundary