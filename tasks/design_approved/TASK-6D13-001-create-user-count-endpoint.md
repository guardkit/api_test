---
complexity: 5
dependencies: []
feature_id: FEAT-6D13
id: TASK-6D13-001
implementation_mode: task-work
parent_review: TASK-REV-6D13
status: design_approved
task_type: feature
title: Create user count endpoint
wave: 1
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