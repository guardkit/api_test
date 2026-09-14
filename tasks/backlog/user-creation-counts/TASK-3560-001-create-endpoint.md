---
id: TASK-3560-001
title: Create user creation count endpoint
task_type: feature
parent_review: TASK-REV-3560
feature_id: FEAT-3560
wave: 1
implementation_mode: task-work
complexity: 5
dependencies: []
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