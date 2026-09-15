---
complexity: 5
dependencies:
- TASK-A0AE-001
feature_id: FEAT-A0AE
id: TASK-A0AE-002
implementation_mode: task-work
parent_review: TASK-REV-A0AE
status: design_approved
task_type: feature
title: Implement analytics CRUD logic
wave: 2
---

# Implement analytics CRUD logic

Implement the database query logic for daily user creation counts.

## Acceptance Criteria

- [ ] Query returns exactly 7 days of data
- [ ] Data points ordered oldest to newest
- [ ] Handles empty data set by returning 7 days of zero counts
- [ ] Handles partial current day gracefully
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use `src/users/crud.py` for query implementation
- Use SQLAlchemy 2.0 `select()` and `func.count()`
- Ensure query is timezone-aware
- All modified files must pass project-configured lint/format checks with zero errors