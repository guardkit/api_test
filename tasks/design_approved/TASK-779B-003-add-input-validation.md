---
complexity: 4
dependencies:
- TASK-779B-001
feature_id: FEAT-779B
id: TASK-779B-003
implementation_mode: task-work
parent_review: TASK-REV-779B
status: design_approved
task_type: feature
title: Add input validation
wave: 2
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