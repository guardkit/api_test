---
complexity: 4
dependencies:
- TASK-3560-002
- TASK-3560-003
feature_id: FEAT-3560
id: TASK-3560-004
implementation_mode: task-work
parent_review: TASK-REV-3560
status: design_approved
task_type: testing
title: Add endpoint tests
wave: 3
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