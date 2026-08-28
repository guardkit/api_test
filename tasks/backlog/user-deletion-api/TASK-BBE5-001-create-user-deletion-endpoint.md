---
id: TASK-BBE5-001
title: Create user deletion endpoint
task_type: scaffolding
parent_review: TASK-REV-BBE5
feature_id: FEAT-BBE5
wave: 1
implementation_mode: task-work
complexity: 5
dependencies: []
---

## Description

Create the DELETE /users/{user_id} endpoint and wire it to the user service.

## Acceptance Criteria

- [ ] DELETE /users/{user_id} endpoint exists
- [ ] Endpoint returns 204 on successful deletion
- [ ] Endpoint returns 404 for non-existent user
- [ ] Endpoint returns 403 for unauthorized requests
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use the existing user service
- Ensure the endpoint is documented in OpenAPI spec