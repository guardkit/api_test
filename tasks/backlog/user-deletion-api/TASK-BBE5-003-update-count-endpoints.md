---
id: TASK-BBE5-003
title: Update count endpoints for real-time reflection
task_type: feature
parent_review: TASK-REV-BBE5
feature_id: FEAT-BBE5
wave: 3
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-BBE5-002
---

## Description

Update all user count endpoints to reflect deletions in real-time.

## Acceptance Criteria

- [ ] All count endpoints reflect reduced count after deletion
- [ ] Count endpoints are updated to exclude deleted users
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Check all endpoints returning user counts
- Ensure no caching delays affect the count