---
complexity: 5
dependencies:
- TASK-3560-001
feature_id: FEAT-3560
id: TASK-3560-002
implementation_mode: task-work
parent_review: TASK-REV-3560
status: design_approved
task_type: feature
title: Implement count calculation logic
wave: 2
---

## Description

Implement the logic to calculate user creation counts per day for the last 7 days.

## Acceptance Criteria

- Logic correctly calculates counts for each of the last 7 days
- Logic handles missing days by returning zero counts
- Logic is testable in isolation
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use SQLAlchemy 2.0 select/execute patterns
- Ensure the query is efficient
- Add unit tests for the calculation logic