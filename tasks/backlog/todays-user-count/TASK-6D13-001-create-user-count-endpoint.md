---
id: TASK-6D13-001
title: Create user count endpoint
task_type: feature
parent_review: TASK-REV-6D13
feature_id: FEAT-6D13
wave: 1
implementation_mode: task-work
complexity: 5
dependencies: []
status: pending
---

## Description
Create the endpoint that returns the count of users created on the current day.

## Acceptance Criteria
- Endpoint exists at `/users/count-today`
- Returns 200 OK with JSON body `{ "count": N }`
- Response body contains integer count
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes
- Use the existing API routing structure
- Ensure the endpoint is accessible via GET
- Plan for testing integration with data store later