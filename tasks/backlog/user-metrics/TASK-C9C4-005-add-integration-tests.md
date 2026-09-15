---
id: TASK-C9C4-005
title: Add integration tests
task_type: testing
parent_review: TASK-REV-C9C4
feature_id: FEAT-C9C4
wave: 4
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-C9C4-004
---

# Add integration tests

Implement integration tests for the metrics endpoint.

## Acceptance Criteria

- Tests cover all scenarios from the feature spec
- Tests verify the 7-day window and ordering
- Tests verify error handling
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use pytest with the project's test configuration
- Add tests to tests/users/
- Ensure tests are hermetic and do not depend on external state