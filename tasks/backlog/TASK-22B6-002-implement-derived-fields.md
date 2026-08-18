---
id: TASK-22B6-002
title: Implement derived field calculation
task_type: feature
parent_review: TASK-REV-22B
feature_id: FEAT-22B6
wave: 2
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-22B6-001
---

## Acceptance Criteria

- [ ] 'days_since_created' calculated correctly from creation date
- [ ] Calculation handles timezone-aware dates correctly
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use the user creation date field from the database
- Ensure the calculation is performed on the server side
