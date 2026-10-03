---
complexity: 5
dependencies:
- TASK-E592-001
feature_id: FEAT-E592
id: TASK-E592-002
implementation_mode: task-work
parent_review: TASK-REV-E592
status: design_approved
task_type: feature
title: Implement analytics CRUD
wave: 2
---

Implement the database query for user creation counts.

## The words of the request this task serves

> Add a GET /users/created-per-day endpoint that returns the number of users created on each of the last 7 days (today and the six days before it), oldest first, counting soft-deleted users too. Use the existing users table and its created_at column — do not change the user model or add a migration. The endpoint takes no parameters.

## Files to Create

- `src/users/analytics_crud.py`

## Files to Modify

- `src/users/__init__.py`

## Acceptance Criteria

- Query returns counts for the last 7 days (today + 6 preceding)
- Query includes soft-deleted users
- Results are ordered oldest to newest
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

Use the existing `users` table and `created_at` column. Do not add a migration.