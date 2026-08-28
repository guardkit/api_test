---
id: TASK-779B-001
title: Add min_count parameter to endpoint
task_type: declarative
parent_review: TASK-REV-779B
feature_id: FEAT-779B
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
---

## Acceptance Criteria

- [ ] Add `min_count` as an optional query parameter to `GET /users/count-by-domain`
- [ ] Ensure the parameter is treated as an integer
- [ ] Parameter is optional (omitting it returns all domains)
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

This is a declarative task — create the necessary schema/model changes to support the new parameter.

## Seam Tests

No cross-task data dependencies identified for this task.