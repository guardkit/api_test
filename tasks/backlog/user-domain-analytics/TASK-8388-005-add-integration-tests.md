---
id: TASK-8388-005
title: Add integration tests for user endpoints
task_type: testing
parent_review: TASK-REV-8388
feature_id: FEAT-8388
wave: 4
implementation_mode: direct
complexity: 4
dependencies:
  - TASK-8388-004
---

# Add integration tests for user endpoints

Implement integration tests for the user domain analytics and creation endpoints.

## Acceptance Criteria

- [ ] Tests for GET /users/count-by-domain on fresh database
- [ ] Tests for GET /users/count-by-domain on existing database
- [ ] Tests for POST /users on fresh database
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use pytest with httpx for API testing
- All modified files pass project-configured lint/format checks with zero errors