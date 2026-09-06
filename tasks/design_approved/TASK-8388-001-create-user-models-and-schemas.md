---
complexity: 4
dependencies: []
feature_id: FEAT-8388
id: TASK-8388-001
implementation_mode: task-work
parent_review: TASK-REV-8388
status: design_approved
task_type: declarative
title: Create user models and schemas
wave: 1
---

# Create user models and schemas

Implement the Pydantic schemas and SQLAlchemy models for user domain analytics and user creation.

## Acceptance Criteria

- [ ] Pydantic schema for user creation with email validation
- [ ] Pydantic schema for user domain count response
- [ ] SQLAlchemy User model with email and domain fields
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use Pydantic v2 for all schemas
- Ensure models inherit from the shared DeclarativeBase
- Email validation should be robust
- All modified files pass project-configured lint/format checks with zero errors