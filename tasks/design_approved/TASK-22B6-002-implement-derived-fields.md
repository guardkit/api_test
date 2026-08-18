---
complexity: 4
dependencies:
- TASK-22B6-001
feature_id: FEAT-22B6
id: TASK-22B6-002
implementation_mode: task-work
parent_review: TASK-REV-22B
status: design_approved
task_type: feature
title: Implement derived field calculation
wave: 2
---

## Acceptance Criteria

- [ ] 'days_since_created' calculated correctly from creation date
- [ ] Calculation handles timezone-aware dates correctly
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use the user creation date field from the database
- Ensure the calculation is performed on the server side