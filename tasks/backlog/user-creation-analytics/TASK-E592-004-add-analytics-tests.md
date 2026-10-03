---
id: TASK-E592-004
title: Add analytics tests
task_type: testing
parent_review: TASK-REV-E592
feature_id: FEAT-E592
wave: 4
implementation_mode: direct
complexity: 3
dependencies:
  - TASK-E592-003
---

Add tests for the analytics endpoint.

## The words of the request this task serves

> Add a GET /users/created-per-day endpoint that returns the number of users created on each of the last 7 days (today and the six days before it), oldest first, counting soft-deleted users too. Use the existing users table and its created_at column — do not change the user model or add a migration. The endpoint takes no parameters.

## Files to Create

- `tests/users/test_analytics.py`

## Files to Modify

- `tests/conftest.py`

## Acceptance Criteria

- Test verifies 7-day window (today + 6 preceding)
- Test verifies oldest-to-newest ordering
- Test verifies soft-deleted users are included
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

Use the existing test infrastructure.