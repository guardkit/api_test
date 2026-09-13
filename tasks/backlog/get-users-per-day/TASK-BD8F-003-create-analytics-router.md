---
id: TASK-BD8F-003
title: Create analytics router
task_type: feature
parent_review: TASK-REV-BD8F
feature_id: FEAT-BD8F
wave: 3
implementation_mode: direct
complexity: 3
dependencies:
  - TASK-BD8F-002
status: pending
---

## Description

Expose the analytics endpoint via a FastAPI router.

## Acceptance Criteria

- [ ] GET /users/created-per-day endpoint returns correct response shape
- [ ] Endpoint requires authentication
- [ ] All modified files pass project-configured lint/format checks with zero errors
- [ ] All modified files have type annotations on arguments and return values

## Implementation Notes

- Register router in `src/main.py`
- Ensure endpoint is documented with OpenAPI tags
- All modified files pass project-configured lint/format checks with zero errors