---
id: TASK-D49B-001
title: Create user stats schema
task_type: declarative
parent_review: TASK-REV-D49B
feature_id: FEAT-D49B
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
---

## Acceptance Criteria

- [ ] Pydantic schema for daily count response (date, count)
- [ ] Pydantic schema for single day response
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Add schemas to src/users/schemas.py or a new src/users/stats/schemas.py
- Ensure all modified files pass project-configured lint/format checks with zero errors