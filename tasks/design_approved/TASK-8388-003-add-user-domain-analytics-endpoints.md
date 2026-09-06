---
complexity: 5
consumer_context:
- consumes: user_domain_counts
  driver: SQLAlchemy
  format_note: dictionary with domain names as keys and integer counts as values
  framework: FastAPI
  task: TASK-8388-002
dependencies:
- TASK-8388-002
feature_id: FEAT-8388
id: TASK-8388-003
implementation_mode: task-work
parent_review: TASK-REV-8388
status: design_approved
task_type: feature
title: Add user domain analytics endpoints
wave: 3
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