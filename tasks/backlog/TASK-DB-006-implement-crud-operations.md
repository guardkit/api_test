---
id: TASK-DB-006
title: Implement CRUD operations
task_type: feature
parent_review: TASK-REV-4B7D
feature_id: FEAT-DB
wave: 3
implementation_mode: task-work
complexity: 5
dependencies:
- TASK-DB-003
- TASK-DB-004
status: blocked
estimated_minutes: 60
autobuild_state:
  current_turn: 2
  max_turns: 5
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-947C
  base_branch: main
  started_at: '2026-02-26T16:46:26.199538'
  last_updated: '2026-02-26T20:50:49.198728'
  turns:
  - turn: 1
    decision: feedback
    feedback: "- Not all acceptance criteria met:\n  \u2022 `src/users/crud.py` created\
      \ with the following functions:\n  \u2022 All functions use `AsyncSession` with\
      \ proper `await` patterns\n  \u2022 `update_user` uses `exclude_unset=True`\
      \ for partial updates\n  \u2022 `tests/users/test_crud.py` created with tests\
      \ for each CRUD function\n  \u2022 All CRUD tests pass using SQLite in-memory\
      \ test fixtures\n  (1 more)"
    timestamp: '2026-02-26T16:46:26.199538'
    player_summary: '[RECOVERED via git_test_detection] Original error: SDK agent
      error: unknown'
    player_success: true
    coach_success: true
  - turn: 2
    decision: error
    feedback: null
    timestamp: '2026-02-26T18:17:07.342287'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: false
---

# Task: Implement CRUD Operations

## Description

Create functional CRUD operations for the User model in `src/users/crud.py` using async SQLAlchemy queries. Follow functional approach (standalone async functions, no base class).

## Acceptance Criteria

- [ ] `src/users/crud.py` created with the following functions:
  - `create_user(db: AsyncSession, user_in: UserCreate) -> User`
  - `get_user(db: AsyncSession, user_id: UUID) -> User | None`
  - `get_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> Sequence[User]`
  - `get_user_by_email(db: AsyncSession, email: str) -> User | None`
  - `update_user(db: AsyncSession, user_id: UUID, user_in: UserUpdate) -> User | None`
  - `delete_user(db: AsyncSession, user_id: UUID) -> bool`
  - `count_users(db: AsyncSession) -> int`
- [ ] All functions use `AsyncSession` with proper `await` patterns
- [ ] `update_user` uses `exclude_unset=True` for partial updates
- [ ] `tests/users/test_crud.py` created with tests for each CRUD function
- [ ] All CRUD tests pass using SQLite in-memory test fixtures
- [ ] mypy strict mode passes

## Technical Notes

- Use `select()` query style (SQLAlchemy 2.0 pattern)
- Use `session.execute()` + `session.scalars()` for queries
- Use `session.add()` + `session.flush()` + `session.refresh()` for creates
- Handle `IntegrityError` for duplicate email in `create_user`
- Use `model_dump(exclude_unset=True)` for partial updates

## Implementation Notes

Functional CRUD approach - clear, readable, independently testable. No premature abstraction with generic base classes.
