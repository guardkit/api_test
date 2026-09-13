---
id: TASK-BD8F-001
title: Create analytics models and schemas
task_type: declarative
parent_review: TASK-REV-BD8F
feature_id: FEAT-BD8F
wave: 1
implementation_mode: task-work
complexity: 4
dependencies: []
status: pending
---

## Description

Create the Pydantic schemas and SQLAlchemy models required for the user analytics feature.

## Acceptance Criteria

- [ ] Pydantic schema `UserCreationStats` defines the response shape
- [ ] SQLAlchemy model `UserAnalytics` (or existing User model extension) supports creation timestamp queries
- [ ] All modified files pass project-configured lint/format checks with zero errors
- [ ] All modified files have type annotations on arguments and return values

## Implementation Notes

- Use the existing `DeclarativeBase` from `src/db/base.py`
- Ensure schemas are placed in `src/users/schemas.py` or a new `src/analytics/schemas.py`
- All modified files pass project-configured lint/format checks with zero errors