---
id: TASK-9230-002
title: Implement statistics calculation logic
task_type: feature
parent_review: TASK-REV-9230
feature_id: FEAT-9230
wave: 2
implementation_mode: task-work
complexity: 5
dependencies:
  - TASK-9230-001
---

## Description

Implement the logic to calculate user creation counts for the last 7 days.

## Acceptance Criteria

- [ ] Returns exactly seven data points
- [ ] Data points are ordered oldest first
- [ ] Days with no new users return a count of zero
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use SQLAlchemy 2.0 select statements
- Ensure the query is efficient and indexed
- Handle timezones correctly (UTC)