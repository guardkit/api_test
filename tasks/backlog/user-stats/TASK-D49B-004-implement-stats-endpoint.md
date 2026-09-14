---
id: TASK-D49B-004
title: Implement stats endpoint
task_type: feature
parent_review: TASK-REV-D49B
feature_id: FEAT-D49B
wave: 4
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-D49B-003
---

## Acceptance Criteria

- [ ] Endpoint returns JSON array of date/count objects
- [ ] Endpoint handles empty dataset by returning 7 days of zero counts
- [ ] Endpoint includes current day even if incomplete
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Implement endpoint handler in src/users/router.py or stats module
- Ensure all modified files pass project-configured lint/format checks with zero errors