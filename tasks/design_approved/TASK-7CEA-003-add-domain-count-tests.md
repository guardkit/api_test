---
complexity: 4
dependencies:
- TASK-7CEA-002
feature_id: FEAT-7CEA
id: TASK-7CEA-003
implementation_mode: task-work
parent_review: TASK-REV-7CEA
status: design_approved
task_type: testing
title: Add domain count tests
wave: 3
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