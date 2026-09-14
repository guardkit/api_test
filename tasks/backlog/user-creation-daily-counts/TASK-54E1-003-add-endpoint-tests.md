---
id: TASK-54E1-003
title: Add endpoint tests
task_type: testing
parent_review: TASK-REV-54E1
feature_id: FEAT-54E1
wave: 3
implementation_mode: direct
complexity: 3
dependencies:
  - TASK-54E1-002
---

# Add endpoint tests

Add tests for the daily counts endpoint.

## Acceptance Criteria

- [ ] Test returns exactly seven data points
- [ ] Test verifies oldest-to-newest ordering
- [ ] Test verifies 7-day window inclusivity
- [ ] Test verifies non-GET rejection
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use `pytest` with `httpx.AsyncClient`
- Add tests to `tests/users/test_daily_counts.py`