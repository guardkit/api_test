---
id: TASK-D49B-002
title: Implement stats CRUD
task_type: feature
parent_review: TASK-REV-D49B
feature_id: FEAT-D49B
wave: 2
implementation_mode: task-work
complexity: 5
dependencies:
  - TASK-D49B-001
---

## Acceptance Criteria

- [ ] CRUD operations for daily user counts
- [ ] Query returns exactly 7 days of data
- [ ] Query returns data ordered oldest to newest
- [ ] Query handles empty dataset correctly
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Implement in src/users/calculations.py or a new stats module
- Use SQLAlchemy 2.0 select/execute patterns
- Ensure all modified files pass project-configured lint/format checks with zero errors