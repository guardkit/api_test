---
complexity: 5
dependencies:
- TASK-BD8F-001
feature_id: FEAT-BD8F
id: TASK-BD8F-002
implementation_mode: task-work
parent_review: TASK-REV-BD8F
status: design_approved
task_type: feature
title: Implement analytics crud
wave: 2
---

## Description

Implement the CRUD logic for retrieving user creation statistics.

## Acceptance Criteria

- [ ] `get_users_created_per_day` function returns correct counts for last 7 days
- [ ] Data is ordered oldest first
- [ ] All modified files pass project-configured lint/format checks with zero errors
- [ ] All modified files have type annotations on arguments and return values

## Implementation Notes

- Use `select()` and `func.count()` with SQLAlchemy 2.0 syntax
- Ensure the query is async-compatible
- All modified files pass project-configured lint/format checks with zero errors