---
id: TASK-39F6-004
title: Add acceptance tests
task_type: testing
parent_review: TASK-REV-39F6
feature_id: FEAT-39F6
wave: 4
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-39F6-003
---

## Acceptance Criteria

- [ ] Test verifies `deleted_at` column existence and nullability
- [ ] Test verifies user record can have null `deleted_at`
- [ ] Test verifies user record can have non-null `deleted_at`
- [ ] Test verifies `deleted_at` column is not a boolean type
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use pytest with the existing test infrastructure
- Ensure tests are hermetic and do not depend on external state