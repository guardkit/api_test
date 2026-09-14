---
id: TASK-3560-004
title: Add endpoint tests
task_type: testing
parent_review: TASK-REV-3560
feature_id: FEAT-3560
wave: 3
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-3560-002
  - TASK-3560-003
---

## Description

Add integration tests for the user creation count endpoint.

## Acceptance Criteria

- Test returns exactly 7 data points
- Test handles empty history correctly
- Test verifies response format matches contract
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use pytest with httpx
- Add tests to tests/users/
- Ensure tests are hermetic