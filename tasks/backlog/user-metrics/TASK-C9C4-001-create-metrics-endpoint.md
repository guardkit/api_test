---
id: TASK-C9C4-001
title: Create metrics endpoint
task_type: feature
parent_review: TASK-REV-C9C4
feature_id: FEAT-C9C4
wave: 1
implementation_mode: task-work
complexity: 5
dependencies: []
---

# Create metrics endpoint

Implement the GET /users/created-per-day endpoint.

## Acceptance Criteria

- Endpoint returns 200 OK with metrics data
- Response format matches the specification
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Add router.py in src/users/
- Use the existing user repository pattern
- Ensure the endpoint is accessible via the main app router