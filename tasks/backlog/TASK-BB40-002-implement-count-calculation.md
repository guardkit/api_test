---
id: TASK-BB40-002
title: Implement count calculation logic
task_type: feature
parent_review: TASK-REV-BB40
feature_id: FEAT-BB40
wave: 2
implementation_mode: task-work
complexity: 5
dependencies:
  - TASK-BB40-001
status: pending
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