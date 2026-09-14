---
complexity: 3
dependencies:
- TASK-D49B-002
feature_id: FEAT-D49B
glue_intent: true
id: TASK-D49B-003
implementation_mode: direct
parent_review: TASK-REV-D49B
task_type: declarative
title: Add stats router
wave: 3
---

## Acceptance Criteria

- [ ] GET /users/created-per-day endpoint registered
- [ ] Router uses dependency injection for DB session
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Add to src/users/router.py or new router file
- Ensure all modified files pass project-configured lint/format checks with zero errors