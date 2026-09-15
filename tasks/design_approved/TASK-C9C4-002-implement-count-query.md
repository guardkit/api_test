---
complexity: 5
dependencies:
- TASK-C9C4-001
feature_id: FEAT-C9C4
id: TASK-C9C4-002
implementation_mode: task-work
parent_review: TASK-REV-C9C4
status: design_approved
task_type: feature
title: Implement count query logic
wave: 2
---

# Implement count query logic

Implement the query that counts user creations per day for the last 7 days.

## Acceptance Criteria

- Query correctly filters users created in the last 7 days
- Query returns exactly 7 data points including today
- Data points are ordered oldest to newest
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use SQLAlchemy 2.0 select/execute patterns
- Ensure the query handles the 7-day window correctly
- The query should be accessible via the crud.py layer