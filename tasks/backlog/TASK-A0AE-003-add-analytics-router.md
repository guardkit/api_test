---
id: TASK-A0AE-003
title: Add analytics router and endpoint
task_type: feature
parent_review: TASK-REV-A0AE
feature_id: FEAT-A0AE
wave: 3
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-A0AE-002
---

# Add analytics router and endpoint

Expose the analytics data via a GET endpoint.

## Acceptance Criteria

- [ ] GET /users/created-per-day endpoint implemented
- [ ] Endpoint returns 200 OK with correct JSON shape
- [ ] POST to endpoint returns 405 Method Not Allowed
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Add route to `src/users/router.py`
- Use `src/users/schemas.py` for response model
- Ensure route handler is `async def`
- All modified files must pass project-configured lint/format checks with zero errors