---
id: TASK-779B-005
title: Add integration tests
task_type: testing
parent_review: TASK-REV-779B
feature_id: FEAT-779B
wave: 4
implementation_mode: task-work
complexity: 5
dependencies:
  - TASK-779B-002
  - TASK-779B-003
---

## Acceptance Criteria

- [ ] Test that providing a valid `min_count` filters domains correctly
- [ ] Test that omitting `min_count` returns all domains
- [ ] Test that a `min_count` of 0 includes all domains
- [ ] Test that a negative `min_count` returns a 400 Bad Request
- [ ] Test that a `min_count` exceeding 10,000 returns a 400 Bad Request
- [ ] Test that a non-integer `min_count` returns a 400 Bad Request
- [ ] Test that an empty `min_count` returns a 400 Bad Request
- [ ] Test that a very large `min_count` returns no domains
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

Use Hurl for integration tests against the running endpoint.