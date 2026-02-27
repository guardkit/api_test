---
complexity: 4
consumer_context:
- consumes: DATABASE_URL
  driver: asyncpg
  format_note: URL must include +asyncpg dialect suffix for async engine; model imports
    Base from src/db/base.py
  framework: SQLAlchemy async (DeclarativeBase)
  task: TASK-DB-001
dependencies:
- TASK-DB-001
estimated_minutes: 45
feature_id: FEAT-DB
id: TASK-DB-003
implementation_mode: task-work
parent_review: TASK-REV-4B7D
status: design_approved
task_type: feature
title: Create user model and schemas
wave: 2
---

# Task: Create User Model and Schemas

## Description

Create the users feature module with SQLAlchemy ORM model and Pydantic schemas following the project's feature-based organization pattern.

## Acceptance Criteria

- [ ] `src/users/__init__.py` created with public exports
- [ ] `src/users/models.py` created with `User` model:
  - `id`: UUID primary key with server-default `uuid4`
  - `email`: Unique, indexed string (not nullable)
  - `full_name`: Optional string
  - `is_active`: Boolean, default `True`
  - `created_at`: Timestamp with timezone, server-default `now()`
  - `updated_at`: Timestamp with timezone, server-default `now()`, onupdate `now()`
- [ ] `src/users/schemas.py` created with:
  - `UserCreate`: email (EmailStr), full_name (optional)
  - `UserUpdate`: email (optional EmailStr), full_name (optional), is_active (optional)
  - `UserPublic`: all fields with `ConfigDict(from_attributes=True)`
  - `UserList`: items list + total count for pagination
- [ ] `src/users/exceptions.py` created with `UserNotFoundError`, `UserAlreadyExistsError`
- [ ] `requirements/base.txt` includes `email-validator` for Pydantic EmailStr
- [ ] Schema validation tests pass (valid/invalid email, optional fields, from_attributes)
- [ ] mypy strict mode passes on new files

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify DATABASE_URL contract from TASK-DB-001."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("DATABASE_URL")
def test_database_url_format():
    """Verify DATABASE_URL matches the expected format.

    Contract: URL must include +asyncpg dialect suffix for async engine
    Producer: TASK-DB-001
    """
    import os
    value = os.environ.get("DATABASE_URL", "")

    assert value, "DATABASE_URL must not be empty"
    assert "+asyncpg" in value, f"Expected asyncpg dialect in URL, got: {value}"
```

## Technical Notes

- Use SQLAlchemy 2.0 `Mapped[T]` annotation style
- User model inherits from `Base` (from `src/db/base.py`)
- Use `mapped_column()` with appropriate types
- Schemas extend `BaseSchema` from `src/schemas.py` if available

## Implementation Notes

This creates the reference data model for the sample users feature.