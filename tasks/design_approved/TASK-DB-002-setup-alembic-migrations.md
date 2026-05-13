---
autobuild_state:
  base_branch: main
  current_turn: 1
  last_updated: '2026-02-26T16:41:08.512294'
  max_turns: 5
  started_at: '2026-02-26T16:07:08.795042'
  turns:
  - coach_success: true
    decision: approve
    feedback: null
    player_success: true
    player_summary: Implementation via task-work delegation
    timestamp: '2026-02-26T16:07:08.795042'
    turn: 1
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-947C
complexity: 4
dependencies:
- TASK-DB-001
estimated_minutes: 45
feature_id: FEAT-DB
id: TASK-DB-002
implementation_mode: task-work
parent_review: TASK-REV-4B7D
status: design_approved
task_type: scaffolding
title: Set up Alembic migrations
wave: 2
---

# Task: Set Up Alembic Migrations

## Description

Configure Alembic for async SQLAlchemy database migrations at the project root. Create async-aware `env.py` that uses the project's engine configuration and `Base.metadata` for autogeneration.

## Acceptance Criteria

- [ ] `alembic.ini` created at project root with correct configuration
- [ ] `alembic/env.py` created with async migration runner using `run_async()` and `AsyncConnection`
- [ ] `alembic/script.py.mako` created with migration template
- [ ] `alembic/versions/` directory created (empty)
- [ ] `env.py` imports `Base.metadata` from `src/db/base.py` for autogenerate support
- [ ] `env.py` reads `DATABASE_URL` from project Settings (not hardcoded)
- [ ] `alembic check` command runs without errors
- [ ] `requirements/base.txt` verified to include `alembic>=1.12.0`
- [ ] mypy strict mode passes on new files

## Technical Notes

- Use `run_async()` pattern for async engine in `env.py`
- `sqlalchemy.url` in `alembic.ini` should be overridden programmatically in `env.py` from Settings
- Ensure `target_metadata = Base.metadata` is correctly set for autogeneration

## Implementation Notes

Standard Alembic at project root - lowest CLI friction, industry standard pattern.