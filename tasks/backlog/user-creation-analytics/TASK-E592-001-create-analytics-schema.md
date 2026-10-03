---
id: TASK-E592-001
title: Create analytics schema and models
task_type: declarative
parent_review: TASK-REV-E592
feature_id: FEAT-E592
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
---

Create the Pydantic models and SQLAlchemy schema for user creation analytics.

## The words of the request this task serves

> Add a GET /users/created-per-day endpoint that returns the number of users created on each of the last 7 days (today and the six days before it), oldest first, counting soft-deleted users too. Use the existing users table and its created_at column — do not change the user model or add a migration. The endpoint takes no parameters.

## Files to Create

- `src/users/analytics_schemas.py`

## Files to Modify

- `src/users/__init__.py`

## Acceptance Criteria

- Pydantic models define the response shape: `list[dict[str, str | int]]` with `date` (ISO-8601) and `count` (integer) keys
- Models are accessible from `src/users`
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

This is a declarative task — it defines data shapes and does not implement logic.