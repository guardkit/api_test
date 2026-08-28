---
id: TASK-BBE5-004
title: Add deletion acceptance tests
task_type: testing
parent_review: TASK-REV-BBE5
feature_id: FEAT-BBE5
wave: 4
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-BBE5-003
---

## Description

Add Hurl tests for the user deletion endpoint.

## Acceptance Criteria

- [ ] Test: DELETE /users/{user_id} returns 204
- [ ] Test: DELETE /users/non-existent returns 404
- [ ] Test: DELETE /users/{user_id} twice returns 404 on second attempt
- [ ] Test: Count endpoints reflect deletion
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use hurl for API tests
- Ensure tests are hermetic