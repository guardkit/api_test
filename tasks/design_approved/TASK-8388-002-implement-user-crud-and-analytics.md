---
complexity: 6
dependencies:
- TASK-8388-001
feature_id: FEAT-8388
id: TASK-8388-002
implementation_mode: task-work
parent_review: TASK-REV-8388
status: design_approved
task_type: feature
title: Implement user CRUD and analytics logic
wave: 2
---

# Implement user CRUD and analytics logic

Implement the core business logic for user management and domain analytics.

## Acceptance Criteria

- [ ] GET /users/count-by-domain returns domain counts
- [ ] POST /users creates a new user
- [ ] Duplicate email handling returns error
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use SQLAlchemy 2.0 select/execute patterns
- Ensure all modified files pass project-configured lint/format checks with zero errors