---
id: TASK-BBE5-005
title: Update API documentation
task_type: documentation
parent_review: TASK-REV-BBE5
feature_id: FEAT-BBE5
wave: 5
implementation_mode: direct
complexity: 2
dependencies:
  - TASK-BBE5-001
---

## Description

Update OpenAPI specification to include the new DELETE endpoint.

## Acceptance Criteria

- [ ] DELETE /users/{user_id} documented
- [ ] Response codes (204, 404, 403) documented
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Update swagger.yaml or equivalent