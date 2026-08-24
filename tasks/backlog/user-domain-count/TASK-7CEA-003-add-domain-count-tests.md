---
id: TASK-7CEA-003
title: Add domain count tests
task_type: testing
parent_review: TASK-REV-7CEA
feature_id: FEAT-7CEA
wave: 3
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-7CEA-002
status: pending
---

# Add domain count tests

Implement test coverage for the domain count endpoint.

## Acceptance Criteria

- Test happy path (domain counts returned correctly)
- Test empty user set (returns empty list)
- Test negative cases (POST/PUT/DELETE rejected)
- Test edge cases (large domain set, malformed emails)
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use hurl for API endpoint tests
- Ensure tests match scenarios in feature specification
- Add tests to tests/acceptance/
