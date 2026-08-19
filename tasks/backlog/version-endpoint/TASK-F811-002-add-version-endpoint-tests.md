---
id: TASK-F811-002
title: Add version endpoint tests
task_type: testing
parent_review: TASK-REV-F811
feature_id: FEAT-F811
wave: 2
implementation_mode: direct
complexity: 3
dependencies:
  - TASK-F811-001
---

# Add version endpoint tests

Create tests for the `/version` endpoint using Hurl.

## Acceptance Criteria

- [ ] Happy path: `/version` returns correct JSON structure
- [ ] Negative case: unsupported media type returns 406 Not Acceptable
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

Use `tests/version/version.hurl` for test definitions.

## Seam Tests

No cross-task data dependencies identified.