---
id: TASK-BBE5-002
title: Implement user deletion logic
task_type: feature
parent_review: TASK-REV-BBE5
feature_id: FEAT-BBE5
wave: 2
implementation_mode: task-work
complexity: 5
dependencies:
  - TASK-BBE5-001
---

## Description

Implement the core deletion logic in the user service.

## Acceptance Criteria

- [ ] User record is permanently removed from database
- [ ] Deletion is idempotent (second delete returns 404)
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Ensure hard delete as per assumption
- Verify database transaction integrity