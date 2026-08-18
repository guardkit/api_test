---
complexity: 5
dependencies: []
feature_id: FEAT-0CAC
id: TASK-0CAC-001
implementation_mode: task-work
parent_review: TASK-REV-0CAC
status: design_approved
task_type: feature
title: Create recent-users endpoint
wave: 1
---

# Create recent-users endpoint

## Description
Implement the core endpoint logic for retrieving recent users. The endpoint should support a `limit` parameter and return users in newest-first order.

## Acceptance Criteria
- [ ] Endpoint responds to GET `/recent-users`
- [ ] Returns 200 OK on success
- [ ] Returns users in descending order of creation timestamp
- [ ] Default behavior returns 10 users when no limit is specified
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes
- Use the existing user repository pattern
- Ensure the response format matches the feature specification
- Add a seam test for the endpoint boundary