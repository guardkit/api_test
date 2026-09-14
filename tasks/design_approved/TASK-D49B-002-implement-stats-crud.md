---
complexity: 5
dependencies:
- TASK-D49B-001
feature_id: FEAT-D49B
id: TASK-D49B-002
implementation_mode: task-work
parent_review: TASK-REV-D49B
status: design_approved
task_type: feature
title: Implement stats CRUD
wave: 2
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