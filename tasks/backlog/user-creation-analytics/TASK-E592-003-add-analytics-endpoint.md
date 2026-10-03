---
id: TASK-E592-003
title: Add analytics endpoint
task_type: feature
parent_review: TASK-REV-E592
feature_id: FEAT-E592
wave: 3
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-E592-002
---

Expose the analytics query via a GET endpoint.

## The words of the request this task serves

> Add a GET /users/created-per-day endpoint that returns the number of users created on each of the last 7 days (today and the six days before it), oldest first, counting soft-deleted users too. Use the existing users table and its created_at column — do not change the user model or add a migration. The endpoint takes no parameters.

## Files to Create

- `src/users/analytics_router.py`

## Files to Modify

- `src/main.py`

## Acceptance Criteria

- GET /users/created-per-day returns the analytics data
- Response format matches the schema
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

Register the router in `src/main.py`.