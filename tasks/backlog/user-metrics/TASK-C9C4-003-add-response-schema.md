---
id: TASK-C9C4-003
title: Add response schema
task_type: declarative
parent_review: TASK-REV-C9C4
feature_id: FEAT-C9C4
wave: 2
implementation_mode: direct
complexity: 3
dependencies:
  - TASK-C9C4-001
---

# Add response schema

Define the Pydantic schemas for the metrics response.

## Acceptance Criteria

- Schema validates the response format correctly
- Schema includes date and count fields
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Add to src/users/schemas.py
- Ensure the schema is compatible with the router's return type