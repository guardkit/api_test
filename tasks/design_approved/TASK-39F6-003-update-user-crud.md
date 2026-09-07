---
complexity: 5
dependencies:
- TASK-39F6-002
feature_id: FEAT-39F6
id: TASK-39F6-003
implementation_mode: task-work
parent_review: TASK-REV-39F6
status: design_approved
task_type: feature
title: Update user CRUD operations
wave: 3
---

## Acceptance Criteria

- [ ] `get_user` filters out users with `deleted_at` set
- [ ] `list_users` filters out users with `deleted_at` set
- [ ] `count_users_by_domain` filters out deleted users
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Update `crud.py` to include `deleted_at` filter in queries
- Ensure queries are efficient and indexed if necessary