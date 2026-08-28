---
id: TASK-779B-003
title: Add input validation
task_type: feature
parent_review: TASK-REV-779B
feature_id: FEAT-779B
wave: 2
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-779B-001
---

## Acceptance Criteria

- [ ] Reject negative `min_count` values with a 400 Bad Request
- [ ] Reject non-integer `min_count` values with a 400 Bad Request
- [ ] Reject empty `min_count` values with a 400 Bad Request
- [ ] Reject `min_count` exceeding the maximum allowed value (10,000) with a 400 Bad Request
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

Validation should happen at the endpoint level before the service layer is invoked.

## Seam Tests

No cross-task data dependencies identified for this task.