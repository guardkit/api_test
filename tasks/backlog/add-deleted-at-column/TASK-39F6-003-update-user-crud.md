---
id: TASK-39F6-003
title: Update user CRUD operations
task_type: feature
parent_review: TASK-REV-39F6
feature_id: FEAT-39F6
wave: 3
implementation_mode: task-work
complexity: 5
dependencies:
  - TASK-39F6-002
---

## Acceptance Criteria

- [ ] `get_user` filters out users with `deleted_at` set
- [ ] `list_users` filters out users with `deleted_at` set
- [ ] `count_users_by_domain` filters out deleted users
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Update `crud.py` to include `deleted_at` filter in queries
- Ensure queries are efficient and indexed if necessary