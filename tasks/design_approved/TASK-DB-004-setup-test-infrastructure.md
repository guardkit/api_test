---
autobuild_state:
  base_branch: main
  current_turn: 1
  last_updated: '2026-02-26T16:35:40.972933'
  max_turns: 5
  started_at: '2026-02-26T16:07:08.784015'
  turns:
  - coach_success: true
    decision: approve
    feedback: null
    player_success: true
    player_summary: Implementation via task-work delegation
    timestamp: '2026-02-26T16:07:08.784015'
    turn: 1
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-947C
complexity: 5
dependencies:
- TASK-DB-001
estimated_minutes: 60
feature_id: FEAT-DB
id: TASK-DB-004
implementation_mode: task-work
parent_review: TASK-REV-4B7D
status: design_approved
task_type: testing
title: Set up database test infrastructure
wave: 2
---

# Task: Set Up Database Test Infrastructure

## Description

Create async database test fixtures using SQLite in-memory for fast, CI-friendly testing. Update `tests/conftest.py` with database session fixtures and FastAPI dependency overrides.

## Acceptance Criteria

- [ ] `requirements/dev.txt` updated with `aiosqlite>=0.19.0`
- [ ] `tests/conftest.py` updated with:
  - `db_engine` fixture: creates async SQLite in-memory engine with `create_all()`
  - `db_session` fixture: yields `AsyncSession` with per-test transaction rollback
  - `override_get_db` fixture: overrides `get_db` dependency on the FastAPI app
  - `client` and `async_client` fixtures updated to use dependency override
- [ ] All existing tests continue to pass (no regressions)
- [ ] New database fixtures are available for use by subsequent tasks
- [ ] `tests/users/__init__.py` created
- [ ] SQLite compatibility handled (e.g., UUID as String(36) if needed)
- [ ] Each test gets isolated database state (no cross-test contamination)

## Technical Notes

- Use `aiosqlite` as the async SQLite driver for tests
- Use `connect_args={"check_same_thread": False}` for SQLite async compatibility
- Engine fixture should `create_all()` on setup and `drop_all()` on teardown
- Override `get_db` dependency using `app.dependency_overrides`
- Ensure existing health endpoint tests remain unaffected

## Implementation Notes

This is a parallel-safe task - can be developed alongside Alembic setup and user model creation. Provides the test foundation for all subsequent feature tasks.