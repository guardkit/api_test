---
id: TASK-22B6-001
title: Create user summary endpoint
task_type: feature
parent_review: TASK-REV-22B6
feature_id: FEAT-22B6
wave: 1
implementation_mode: task-work
complexity: 5
dependencies: []
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
