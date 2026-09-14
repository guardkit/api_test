---
id: TASK-D49B-005
title: Add stats tests
task_type: testing
parent_review: TASK-REV-D49B
feature_id: FEAT-D49B
wave: 5
implementation_mode: direct
complexity: 3
dependencies:
  - TASK-D49B-004
---

## Acceptance Criteria

- [ ] Test: response contains exactly seven data points
- [ ] Test: oldest day is first entry
- [ ] Test: most recent day is last entry
- [ ] Test: POST request is rejected
- [ ] Test: response contains zero counts when no users created
- [ ] Test: response includes current day even if incomplete
- [ ] Test: response body is JSON array
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Add tests to tests/users/test_stats.py
- Ensure all modified files pass project-configured lint/format checks with zero errors