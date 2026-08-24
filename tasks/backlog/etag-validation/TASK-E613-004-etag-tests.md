---
id: TASK-E613-004
title: Add ETag acceptance tests
task_type: testing
parent_review: TASK-REV-E613-PLAN
feature_id: FEAT-E613
wave: 4
implementation_mode: direct
complexity: 3
dependencies:
  - TASK-E613-003
status: pending
---

# Add ETag acceptance tests

## Acceptance Criteria

- All scenarios in the feature specification are covered
- Tests verify strong ETag generation
- Tests verify 304 response for matching If-None-Match
- Tests verify full response for non-matching or missing headers
- Tests verify handling of malformed headers
- Tests verify stale ETag (resource change) behavior
- Tests verify concurrent request behavior
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use Hurl for acceptance tests as per routing recommendation
- Ensure test data setup includes user with known state
- Test concurrency with at least two simultaneous requests

## Seam Tests

No seam tests required for this task.