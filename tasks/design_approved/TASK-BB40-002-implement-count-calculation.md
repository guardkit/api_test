---
complexity: 5
dependencies:
- TASK-BB40-001
feature_id: FEAT-BB40
id: TASK-BB40-002
implementation_mode: task-work
parent_review: TASK-REV-BB40
status: design_approved
task_type: feature
title: Implement count calculation logic
wave: 2
---

## Description

Implement the logic to calculate user creation counts for the last 7 days.

## Acceptance Criteria

- Logic correctly identifies the last 7 days including today
- Counts are accurate based on user creation timestamps
- Empty days return zero count
- Logic is testable in isolation

## Implementation Notes

- Use SQLAlchemy 2.0 select/execute patterns
- Ensure the query is efficient
- Add unit tests for the calculation logic