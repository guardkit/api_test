---
complexity: 5
dependencies:
- TASK-8C46-001
feature_id: FEAT-8C46
id: TASK-8C46-002
implementation_mode: task-work
parent_review: TASK-REV-8C46
status: design_approved
task_type: feature
title: Implement domain discovery endpoint
wave: 2
---

Implement the GET /users/domains endpoint.

## The words of the request this task serves

> Add a GET /users/domains endpoint that returns a sorted list of distinct email domains in alphabetical order.

## Files to Create

- `src/users/router.py` (if not already present, or add route to existing)

## Files to Modify

- `src/users/crud.py`
- `src/users/schemas.py`

## Acceptance Criteria

- GET /users/domains returns a JSON array of unique domains
- Domains are returned in alphabetical order
- Empty domain list returns an empty array
- Concurrent requests both succeed
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use the domain extraction utility
- Ensure the endpoint is async
- Return a Pydantic model, not a raw dictionary