---
id: TASK-8388-003
title: Add user domain analytics endpoints
task_type: feature
parent_review: TASK-REV-8388
feature_id: FEAT-8388
wave: 3
implementation_mode: task-work
complexity: 5
dependencies:
  - TASK-8388-002
consumer_context:
  - task: TASK-8388-002
    consumes: user_domain_counts
    framework: FastAPI
    driver: SQLAlchemy
    format_note: dictionary with domain names as keys and integer counts as values
---

# Add user domain analytics endpoints

Expose the domain analytics functionality via an API endpoint.

## Acceptance Criteria

- [ ] GET /users/count-by-domain endpoint implemented
- [ ] Endpoint returns correct counts for each domain
- [ ] Endpoint handles invalid query parameters
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Ensure the endpoint is accessible via the router
- All modified files pass project-configured lint/format checks with zero errors