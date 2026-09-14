---
id: TASK-54E1-002
title: Add daily counts endpoint
task_type: feature
parent_review: TASK-REV-54E1
feature_id: FEAT-54E1
wave: 2
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-54E1-001
consumer_context:
  - task: TASK-54E1-001
    consumes: daily_counts_response
    framework: FastAPI
    driver: SQLAlchemy async
    format_note: "List of objects with date (ISO 8601) and count (integer)"
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