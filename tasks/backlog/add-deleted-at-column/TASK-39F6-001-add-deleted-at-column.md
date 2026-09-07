---
id: TASK-39F6-001
title: Add deleted_at column to users table
task_type: declarative
parent_review: TASK-REV-39F6
feature_id: FEAT-39F6
wave: 1
implementation_mode: direct
complexity: 4
dependencies: []
---

## Acceptance Criteria

- [ ] Database migration adds `deleted_at` column to `users` table
- [ ] `deleted_at` column is nullable
- [ ] `deleted_at` column is of timestamp type
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use Alembic for the migration
- Ensure the migration is backward compatible
- The column should be nullable to support existing records