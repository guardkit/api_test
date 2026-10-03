---
id: TASK-651C-004
title: Add active count tests
task_type: testing
parent_review: TASK-REV-651C
feature_id: FEAT-651C
wave: 4
implementation_mode: direct
complexity: 3
dependencies:
  - TASK-651C-003
---

Add tests for the active count endpoint.

## The words of the request this task serves

> Add a GET /users/active-count endpoint that returns the number of active and inactive users as separate counts.

## Files to Create

- `tests/users/test_active_count.py`

## Files to Modify

- `tests/conftest.py` (if needed for test setup)

## Acceptance Criteria

- Test verifies active count is correct for non-empty user set
- Test verifies inactive count is correct for non-empty user set
- Test verifies both counts are 0 when no users exist
- Test verifies POST request is rejected
- Test verifies invalid path is rejected
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

Use TestClient or httpx to call the endpoint. Seed the database with test users of different statuses.