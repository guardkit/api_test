---
complexity: 4
dependencies:
- TASK-BBE5-003
feature_id: FEAT-BBE5
id: TASK-BBE5-004
implementation_mode: task-work
parent_review: TASK-REV-BBE5
status: design_approved
task_type: testing
title: Add deletion acceptance tests
wave: 4
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