---
complexity: 5
dependencies: []
feature_id: FEAT-54E1
id: TASK-54E1-001
implementation_mode: task-work
parent_review: TASK-REV-54E1
status: design_approved
task_type: feature
title: Implement user creation count query
wave: 1
---

# Implement user creation count query

Implement the database query to count user creations per day for the last 7 days.

## Acceptance Criteria

- [ ] Query returns exactly 7 data points for the last 7 days
- [ ] Data points are ordered oldest first
- [ ] The 7-day window is inclusive of the oldest day
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use SQLAlchemy 2.0 `select()` syntax
- Ensure the query is efficient and uses an index on `created_at`
- The query should be implemented in `src/users/crud.py`