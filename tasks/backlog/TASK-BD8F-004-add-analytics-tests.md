---
id: TASK-BD8F-004
title: Add analytics tests
task_type: testing
parent_review: TASK-REV-BD8F
feature_id: FEAT-BD8F
wave: 4
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-BD8F-003
status: pending
---

## Description

Add test coverage for the analytics endpoint.

## Acceptance Criteria

- [ ] Test verifies exactly seven days of data are returned
- [ ] Test verifies data is ordered oldest first
- [ ] Test verifies boundary conditions for date range
- [ ] Test verifies negative cases (method, authentication)
- [ ] All modified files pass project-configured lint/format checks with zero errors
- [ ] All modified files have type annotations on arguments and return values

## Implementation Notes

- Use `pytest` with `httpx.AsyncClient`
- Target `tests/users/` directory
- All modified files pass project-configured lint/format checks with zero errors