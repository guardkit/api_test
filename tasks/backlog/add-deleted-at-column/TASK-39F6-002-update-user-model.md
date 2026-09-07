---
id: TASK-39F6-002
title: Update user model and schemas
task_type: declarative
parent_review: TASK-REV-39F6
feature_id: FEAT-39F6
wave: 2
implementation_mode: direct
complexity: 3
dependencies:
  - TASK-39F6-001
---

## Acceptance Criteria

- [ ] User model includes `deleted_at` field
- [ ] User schemas include `deleted_at` field
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Update `models.py` to include the new column
- Update Pydantic schemas to include `deleted_at`