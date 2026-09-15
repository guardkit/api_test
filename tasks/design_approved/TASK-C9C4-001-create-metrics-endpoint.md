---
complexity: 5
dependencies: []
feature_id: FEAT-C9C4
id: TASK-C9C4-001
implementation_mode: task-work
parent_review: TASK-REV-C9C4
status: design_approved
task_type: feature
title: Create metrics endpoint
wave: 1
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