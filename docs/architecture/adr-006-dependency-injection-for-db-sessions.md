# ADR-006: Dependency Injection for Database Session Lifecycle Management

## Status
Accepted

## Context
The application requires a consistent pattern for acquiring and releasing database sessions across different feature modules. Without a centralized dependency mechanism, each route would need to manually manage session creation, error handling, and closure, leading to connection leaks and inconsistent transaction boundaries.

## Decision
Use FastAPI's dependency injection system to manage the lifecycle of SQLAlchemy database sessions. Specifically:
- Define a dependency function that yields a session from the session factory.
- Inject this dependency into router functions using `Depends`.
- Ensure the session is automatically closed after the request lifecycle completes.

## Consequences
- **What it makes easy**: Testability via dependency overrides, consistent session cleanup, and simplified route signatures.
- **What it forbids**: Direct instantiation of `Session` objects within business logic or router handlers.
- **Trade-off**: Requires all database-interacting routes to follow the dependency pattern rather than using global session objects.

## Evidence
- `src/db/dependencies.py`: Contains the session dependency definition.
- `src/db/session.py`: Manages the SQLAlchemy session factory and engine configuration.
- `src/users/router.py` (and other feature routers): Uses `Depends(get_db)` to inject sessions into endpoints.
- `src/db/base.py`: Provides the SQLAlchemy base class used by models.
