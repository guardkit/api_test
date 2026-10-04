---
id: TASK-8C46-003
title: Add domain discovery tests
task_type: testing
parent_review: TASK-REV-8C46
feature_id: FEAT-8C46
wave: 3
implementation_mode: direct
complexity: 3
dependencies:
  - TASK-8C46-002
---

Add tests for the domain discovery endpoint.

## The words of the request this task serves

> Add a GET /users/domains endpoint that returns a sorted list of distinct email domains in alphabetical order.

## Files to Create

- `tests/users/test_domain_discovery.py`

## Files to Modify

- `tests/conftest.py`

## Acceptance Criteria

- Test verifies happy path (sorted list)
- Test verifies empty state (empty list)
- Test verifies malformed email handling
- Test verifies concurrent request handling
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use pytest with httpx for endpoint testing
- Ensure tests are hermetic