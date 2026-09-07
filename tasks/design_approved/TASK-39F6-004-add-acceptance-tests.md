---
complexity: 4
dependencies:
- TASK-39F6-003
feature_id: FEAT-39F6
id: TASK-39F6-004
implementation_mode: task-work
parent_review: TASK-REV-39F6
status: design_approved
task_type: testing
title: Add acceptance tests
wave: 4
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