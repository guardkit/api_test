---
id: TASK-DB-001
title: "Create database infrastructure"
task_type: scaffolding
parent_review: TASK-REV-4B7D
feature_id: FEAT-DB
wave: 1
implementation_mode: task-work
complexity: 5
dependencies: []
status: pending
estimated_minutes: 60
---

# Task: Create Database Infrastructure

## Description

Set up the core database infrastructure in `src/db/` including async SQLAlchemy engine with connection pooling, session factory, FastAPI dependency, and configuration settings.

## Acceptance Criteria

- [ ] `src/db/__init__.py` created with public exports
- [ ] `src/db/base.py` created with `DeclarativeBase` subclass including common columns (id as UUID, created_at, updated_at)
- [ ] `src/db/session.py` created with `create_async_engine()`, `async_sessionmaker`, pool configuration, `init_engine()` and `dispose_engine()` functions
- [ ] `src/db/dependencies.py` created with `get_db()` async generator FastAPI dependency yielding `AsyncSession`
- [ ] `src/core/config.py` updated with database settings: `database_url`, `db_pool_size`, `db_max_overflow`, `db_pool_timeout`, `db_pool_recycle`, `db_echo`
- [ ] `src/main.py` lifespan handler updated to initialize engine on startup and dispose on shutdown
- [ ] `.env.example` updated with `DATABASE_URL=postgresql+asyncpg://postgres:test@localhost:5432/test`
- [ ] `requirements/base.txt` verified to include `sqlalchemy>=2.0.0`, `asyncpg>=0.29.0`
- [ ] All existing tests continue to pass
- [ ] mypy strict mode passes on new files

## Technical Notes

- Use SQLAlchemy 2.0 `Mapped[T]` annotation style for mypy compatibility
- Pool settings exposed via `Settings` class (Pydantic BaseSettings)
- Engine lifecycle tied to FastAPI lifespan (no leaked connections)
- Use `uuid4` server-default for UUID primary keys
- Use `func.now()` for timestamp defaults

## Implementation Notes

This is a foundation task - all other database tasks depend on this one.
