---
complexity: 5
dependencies: []
feature_id: FEAT-3560
id: TASK-3560-001
implementation_mode: task-work
parent_review: TASK-REV-3560
status: design_approved
task_type: feature
title: Create user creation count endpoint
wave: 1
---

## Description

Create the GET /users/created-per-day endpoint in the users module.

## Acceptance Criteria

- Endpoint returns JSON array of date-count pairs
- Response contains exactly 7 data points for the last 7 days
- Endpoint handles empty history by returning zero counts for missing days
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use the existing users router
- Ensure the endpoint is documented in the API spec
- Add to the feature's test suite