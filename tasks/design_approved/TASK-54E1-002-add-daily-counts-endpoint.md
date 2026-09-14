---
complexity: 4
consumer_context:
- consumes: daily_counts_response
  driver: SQLAlchemy async
  format_note: List of objects with date (ISO 8601) and count (integer)
  framework: FastAPI
  task: TASK-54E1-001
dependencies:
- TASK-54E1-001
feature_id: FEAT-54E1
id: TASK-54E1-002
implementation_mode: task-work
parent_review: TASK-REV-54E1
status: design_approved
task_type: feature
title: Add daily counts endpoint
wave: 2
---

# Add daily counts endpoint

Expose the user creation counts via a GET endpoint.

## Acceptance Criteria

- [ ] GET /users/created-per-day returns the counts
- [ ] Response format matches the integration contract
- [ ] Non-GET requests are rejected with 405
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Add route to `src/users/router.py`
- Use the Pydantic model from `src/users/schemas.py`
- Ensure the endpoint is documented in OpenAPI