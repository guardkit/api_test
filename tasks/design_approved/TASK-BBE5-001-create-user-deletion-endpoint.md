---
complexity: 5
dependencies: []
feature_id: FEAT-BBE5
id: TASK-BBE5-001
implementation_mode: task-work
parent_review: TASK-REV-BBE5
status: design_approved
task_type: scaffolding
title: Create user deletion endpoint
wave: 1
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