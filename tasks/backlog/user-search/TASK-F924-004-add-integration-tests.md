---
id: TASK-F924-004
title: Add integration tests
task_type: testing
parent_review: TASK-REV-F904
feature_id: FEAT-F904
wave: 4
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-F924-003
---

## Description

Add integration tests covering the key scenarios defined in the feature spec.

## Acceptance Criteria

- [ ] Test: partial name match returns correct users
- [ ] Test: case-insensitive matching works
- [ ] Test: empty query returns all users
- [ ] Test: single character query works
- [ ] Test: no matches returns empty list
- [ ] Test: special characters handled literally
- [ ] Test: whitespace-only query returns all users
- [ ] Test: missing parameter returns error
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use the existing integration test framework
- Target the `tests/users/test_search.py` path
- Ensure tests are runnable via `pytest`