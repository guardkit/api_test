---
complexity: 5
dependencies: []
feature_id: FEAT-22B6
id: TASK-22B6-001
implementation_mode: task-work
parent_review: TASK-REV-22B6
status: design_approved
task_type: feature
title: Create user summary endpoint
wave: 1
---

## Acceptance Criteria

- [ ] GET /users/{user_id}/summary returns 200 for valid user
- [ ] Response contains username, display name, and profile metadata
- [ ] Response includes 'days_since_created' as integer
- [ ] Response includes 'is_active' boolean
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use the existing user repository for data access
- Ensure the endpoint is documented in the API reference