---
id: TASK-B539-001
title: Add user_creation_count query to crud.py
task_type: declarative
parent_review: TASK-REV-B539
feature_id: FEAT-B539
wave: 1
implementation_mode: direct
complexity: 4
dependencies: []
---

# Add user_creation_count query to crud.py

Implement the database query to count users created per day for the last 7 days.

## Acceptance Criteria

- [ ] Query returns exactly 7 data points for the last 7 days
- [ ] Data points are ordered oldest to newest
- [ ] Each data point includes a date and a count
- [ ] Handles systems running for less than 7 days by returning zero counts for missing days
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use SQLAlchemy 2.0 select/execute pattern
- Ensure query is timezone-aware (UTC)
- Add to src/users/crud.py