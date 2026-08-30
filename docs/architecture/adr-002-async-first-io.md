# ADR-002: Async-first I/O operations

## Status
Accepted

## Context
The api_test service is a FastAPI application designed for production-ready performance. FastAPI is built on Starlette and is natively asynchronous, meaning blocking I/O operations in route handlers can starve the event loop and degrade throughput. To fully leverage the framework's concurrency model, I/O operations must be non-blocking.

## Decision
All I/O-bound operations—including database queries, external API calls, and file system access—must use `async` and `await`. Synchronous blocking calls are forbidden in route handlers and service layers.

## Consequences
- **What it makes easy**: High concurrency handling with minimal resource overhead; seamless integration with async database drivers; straightforward use of `httpx` for external calls.
- **What it forbids**: Using blocking libraries (e.g., `requests`, standard `psycopg2`) inside async routes; performing long-running CPU-bound tasks directly on the event loop without offloading.
- **What it requires**: Developers must ensure all database access uses an async driver and that all service-layer functions are defined as `async def`.

## Evidence
- `src/db/session.py` implements async session management.
- `src/users/crud.py` uses async database operations.
- `src/main.py` and route handlers in `src/users/router.py`, `src/search/router.py`, etc., use `async def`.
- The technology stack explicitly specifies `asyncpg` as the recommended async PostgreSQL driver.
