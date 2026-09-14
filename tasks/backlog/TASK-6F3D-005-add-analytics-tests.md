---
id: TASK-6F3D-005
title: Add analytics integration tests
task_type: testing
parent_review: TASK-REV-6F3D
feature_id: FEAT-6F3D
wave: 5
implementation_mode: direct
complexity: 3
dependencies:
  - TASK-6F3D-004
status: pending
---

# Add analytics integration tests

Implement tests covering all scenarios from the feature specification.

## Acceptance Criteria

- [ ] Happy path: 7 days of data returned
- [ ] Boundary: exactly 7 days returned
- [ ] Boundary: no more than 7 days returned
- [ ] Negative: empty data returns 7 days with zero counts
- [ ] Negative: POST request rejected
- [ ] Edge case: valid JSON response
- [ ] Edge case: strict date ordering
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use pytest with httpx for endpoint testing
- Ensure tests are hermetic and use test database
- All modified files pass project-configured lint/format checks with zero errors