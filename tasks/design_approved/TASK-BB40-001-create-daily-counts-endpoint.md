---
complexity: 4
dependencies: []
feature_id: FEAT-BB40
id: TASK-BB40-001
implementation_mode: task-work
parent_review: TASK-REV-BB40
status: design_approved
task_type: feature
title: Create daily counts endpoint
wave: 1
---

## Description

Create the GET /users/created-per-day endpoint that returns user creation counts for the last 7 days.

## Acceptance Criteria

- Endpoint returns exactly seven data points
- Data points are ordered oldest to newest
- Each data point includes a date and count
- Endpoint handles empty data correctly (returns zeros)
- Endpoint rejects non-GET methods with 405
- Endpoint handles database unavailability gracefully

## Implementation Notes

- Use the existing router pattern
- Ensure the endpoint is documented in the API spec
- Add a smoke test for the happy path