---
complexity: 5
dependencies:
- TASK-6F3D-003
feature_id: FEAT-6F3D
id: TASK-6F3D-004
implementation_mode: task-work
parent_review: TASK-REV-6F3D
status: design_approved
task_type: feature
title: Implement analytics service logic
wave: 4
---

# Implement analytics service logic

Orchestrate the data retrieval and formatting for the analytics endpoint.

## Acceptance Criteria

- [ ] Service correctly calculates 7-day window
- [ ] Data points correctly formatted as ISO-8601 dates
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Keep service logic testable without database
- All modified files pass project-configured lint/format checks with zero errors