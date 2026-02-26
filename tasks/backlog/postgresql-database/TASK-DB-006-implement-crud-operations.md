---
id: TASK-DB-006
title: "Implement CRUD operations"
task_type: feature
parent_review: TASK-REV-4B7D
feature_id: FEAT-DB
wave: 3
implementation_mode: task-work
complexity: 5
dependencies:
  - TASK-DB-003
  - TASK-DB-004
status: pending
estimated_minutes: 60
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
