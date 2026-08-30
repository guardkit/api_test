# ADR-004: SQLAlchemy 2.0 with Async Drivers

## Status
Accepted

## Context
The application requires a database layer that supports asynchronous I/O to align with FastAPI's async-first architecture. The architecture guide specifies SQLAlchemy >=2.0.0 and recommends asyncpg as the async PostgreSQL driver. This ensures non-blocking database operations during request handling.

## Decision
All database operations must use SQLAlchemy 2.0 with async drivers. This includes:
- Using `AsyncSession` for all database interactions.
- Leveraging SQLAlchemy 2.0's `select()` and `execute()` patterns rather than legacy query objects.
- Defining models using the `DeclarativeBase` pattern.
- Managing sessions via FastAPI dependencies.

## Consequences
- **Makes**: High-performance async database operations, type-safe queries, and seamless integration with FastAPI's async lifecycle.
- **Forbids**: Synchronous database calls, legacy SQLAlchemy 1.x query syntax, and direct connection management outside the dependency injection system.

## Evidence
- `src/db/session.py` implements async session management.
- `src/db/base.py` defines the SQLAlchemy base class.
- `src/users/crud.py` demonstrates async database operations.
- `src/db/dependencies.py` provides async session injection.
- `src/main.py` initializes the application with async database configurations.
