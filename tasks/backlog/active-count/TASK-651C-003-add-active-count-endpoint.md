---
id: TASK-651C-003
title: Add active count endpoint
task_type: feature
parent_review: TASK-REV-651C
feature_id: FEAT-651C
wave: 3
implementation_mode: direct
complexity: 3
dependencies:
  - TASK-651C-002
---

Expose the active count query via a GET /users/active-count endpoint.

## The words of the request this task serves

> Add a GET /users/active-count endpoint that returns the number of active and inactive users as separate counts.

## Files to Create

- `src/users/router.py` (if not existing, or append to it)

## Files to Modify

- `src/users/router.py`

## Acceptance Criteria

- GET /users/active-count returns 200 OK with the active/inactive counts
- Response format matches the schema from TASK-651C-001
- Endpoint is read-only (POST/PUT/DELETE return 405 or 404)
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

Register the route in the existing FastAPI router. Ensure it uses the CRUD function from TASK-651C-002.