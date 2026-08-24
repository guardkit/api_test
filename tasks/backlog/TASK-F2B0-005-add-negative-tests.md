---
id: TASK-F2B0-005
title: Add negative tests
task_type: testing
parent_review: TASK-REV-F2B0
feature_id: FEAT-F2B0
wave: 4
implementation_mode: direct
complexity: 3
dependencies:
  - TASK-F2B0-004
status: pending
---

# Add negative tests

## Acceptance Criteria

- [ ] Verify "A user ID that does not exist returns a not found response"
- [ ] Verify "An empty user ID returns a bad request error"
- [ ] Verify "A user ID containing special characters is rejected"
- [ ] Verify "A validly formatted ID that is not present returns not found"
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Ensure negative scenarios cover all boundary conditions defined in spec
- Use hurl for API testing
