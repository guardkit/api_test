---
complexity: 4
dependencies:
- TASK-BBE5-002
feature_id: FEAT-BBE5
id: TASK-BBE5-003
implementation_mode: task-work
parent_review: TASK-REV-BBE5
status: design_approved
task_type: feature
title: Update count endpoints for real-time reflection
wave: 3
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