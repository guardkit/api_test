---
complexity: 4
dependencies:
- TASK-6F3D-002
feature_id: FEAT-6F3D
glue_intent: true
id: TASK-6F3D-003
implementation_mode: task-work
parent_review: TASK-REV-6F3D
status: pending
task_type: feature
title: Add analytics router and endpoint
wave: 3
---

# Add analytics router and endpoint

Expose the analytics endpoint via FastAPI router.

## Acceptance Criteria

- [ ] GET /users/created-per-day endpoint implemented
- [ ] Response matches Pydantic schema
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use dependency injection for database session
- Ensure route handler is async def
- All modified files pass project-configured lint/format checks with zero errors