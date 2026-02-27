---
id: TASK-DB-005
title: Create initial database migration
task_type: feature
parent_review: TASK-REV-4B7D
feature_id: FEAT-DB
wave: 3
implementation_mode: direct
complexity: 2
dependencies:
- TASK-DB-002
- TASK-DB-003
status: in_review
estimated_minutes: 20
autobuild_state:
  current_turn: 2
  max_turns: 5
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-947C
  base_branch: main
  started_at: '2026-02-26T16:46:26.195439'
  last_updated: '2026-02-26T19:02:22.838134'
  turns:
  - turn: 1
    decision: feedback
    feedback: "- Not all acceptance criteria met:\n  \u2022 `alembic/versions/001_create_users_table.py`\
      \ created via `alembic revision --autogenerate`\n  \u2022 Migration creates\
      \ `users` table with all columns (id, email, full_name, is_active, created_at,\
      \ updat\n  \u2022 Migration includes unique constraint on email column\n  \u2022\
      \ Migration includes index on email column\n  \u2022 `alembic upgrade head`\
      \ applies cleanly\n  (1 more)"
    timestamp: '2026-02-26T16:46:26.195439'
    player_summary: 'Created initial database migration for the FastAPI backend. Key
      changes:


      1. **src/db/base.py**: Added `metadata = mapper_registry.metadata` to expose
      the registry''s metadata on DeclarativeBase, enabling Alembic to discover models.


      2. **src/db/dependencies.py**: No functional changes - the get_db dependency
      remains unchanged.


      3. **src/users/models.py**: Refactored User model to use `@mapper_registry.mapped`
      decorator pattern instead of inheriting from DeclarativeBase, which is required
      for mod'
    player_success: true
    coach_success: true
  - turn: 2
    decision: approve
    feedback: null
    timestamp: '2026-02-26T18:06:28.643992'
    player_summary: 'Direct mode SDK invocation completed (git-detected: 30 modified,
      2 created)'
    player_success: true
    coach_success: true
---

# Task: Create Initial Database Migration

## Description

Generate the initial Alembic migration for the users table using autogenerate from the User model.

## Acceptance Criteria

- [ ] `alembic/versions/001_create_users_table.py` created via `alembic revision --autogenerate`
- [ ] Migration creates `users` table with all columns (id, email, full_name, is_active, created_at, updated_at)
- [ ] Migration includes unique constraint on email column
- [ ] Migration includes index on email column
- [ ] `alembic upgrade head` applies cleanly
- [ ] `alembic downgrade base` rolls back cleanly

## Technical Notes

- Run `alembic revision --autogenerate -m "create users table"` to generate
- Verify the generated migration matches the User model definition
- Test both upgrade and downgrade paths

## Implementation Notes

Short task - depends on both Alembic setup and User model being complete.
