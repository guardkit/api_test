---
id: TASK-8C46-001
title: Create domain extraction utility
task_type: declarative
parent_review: TASK-REV-8C46
feature_id: FEAT-8C46
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
---

Implement a utility to extract email domains from user email addresses.

## The words of the request this task serves

> Add a GET /users/domains endpoint that returns a sorted list of distinct email domains in alphabetical order.

## Files to Create

- `src/users/domain_extraction.py`

## Files to Modify

- `src/users/models.py`

## Acceptance Criteria

- Utility correctly extracts domain from valid email addresses
- Utility handles malformed email addresses gracefully
- Utility is testable in isolation
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use a simple regex or string splitting for extraction
- Ensure the utility is available for use by the endpoint implementation