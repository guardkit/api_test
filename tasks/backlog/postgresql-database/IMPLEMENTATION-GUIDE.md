# Implementation Guide: PostgreSQL Database Integration

## Overview

Add PostgreSQL database integration using SQLAlchemy async with connection pooling, health check integration, and a sample users table with CRUD endpoints.

**Feature ID**: FEAT-DB
**Review Task**: TASK-REV-4B7D
**Total Subtasks**: 8
**Estimated Effort**: 13-18 hours
**Overall Complexity**: 6/10

## Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| DB Connection | Centralized `src/db/` module | Aligns with CLAUDE.md, clean separation |
| Project Structure | Minimal users feature (router, schemas, models, crud, exceptions) | Pragmatic - only meaningful files |
| Health Check | Inline DB probe in existing endpoint | Simple, single endpoint, easily upgradeable |
| Migrations | Standard Alembic at project root | Industry standard, lowest CLI friction |
| CRUD Pattern | Functional async functions | Clear, readable, no premature abstraction |
| Test DB | SQLite async in-memory | No Docker required, CI-friendly |

## Data Flow: Read/Write Paths

```mermaid
flowchart LR
    subgraph Writes["Write Paths"]
        W1["POST /users\ncreate_user()"]
        W2["PUT /users/{id}\nupdate_user()"]
        W3["DELETE /users/{id}\ndelete_user()"]
        W4["Alembic\nmigrate"]
    end

    subgraph Storage["Storage"]
        S1[("PostgreSQL\nusers table")]
        S2[("Connection Pool\nasync engine")]
    end

    subgraph Reads["Read Paths"]
        R1["GET /users\nget_users()"]
        R2["GET /users/{id}\nget_user()"]
        R3["GET /health\nSELECT 1"]
    end

    W1 -->|"INSERT via AsyncSession"| S1
    W2 -->|"UPDATE via AsyncSession"| S1
    W3 -->|"DELETE via AsyncSession"| S1
    W4 -->|"DDL schema changes"| S1

    S2 -->|"provides sessions"| S1

    S1 -->|"SELECT via get_users()"| R1
    S1 -->|"SELECT via get_user()"| R2
    S2 -->|"SELECT 1 probe"| R3

    style S2 fill:#ccf,stroke:#009
```

_All write paths have corresponding read paths. No disconnections detected._

## Integration Contracts

```mermaid
sequenceDiagram
    participant Client as HTTP Client
    participant Router as users/router.py
    participant CRUD as users/crud.py
    participant Session as db/dependencies.py
    participant Engine as db/session.py
    participant PG as PostgreSQL

    Client->>Router: POST /users {email, name}
    Router->>Session: get_db() dependency
    Session->>Engine: async_sessionmaker()
    Engine->>PG: acquire connection from pool
    PG-->>Engine: connection
    Engine-->>Session: AsyncSession
    Session-->>Router: db session

    Router->>CRUD: create_user(db, user_in)
    CRUD->>PG: INSERT INTO users
    PG-->>CRUD: user row
    CRUD-->>Router: User object
    Router-->>Client: 201 UserPublic

    Note over Router,Session: Session auto-closed via dependency cleanup

    Client->>Router: GET /health
    Router->>Session: get_db() dependency
    Session-->>Router: db session
    Router->>PG: SELECT 1
    PG-->>Router: result
    Router-->>Client: 200 {status: ok, database: connected}
```

_Shows the full request lifecycle from HTTP client through router, CRUD, session dependency, engine, to PostgreSQL and back._

## Task Dependencies

```mermaid
graph TD
    T1[TASK-DB-001<br/>Database Infrastructure] --> T2[TASK-DB-002<br/>Alembic Setup]
    T1 --> T3[TASK-DB-003<br/>User Model & Schemas]
    T1 --> T4[TASK-DB-004<br/>Test Infrastructure]
    T1 --> T8[TASK-DB-008<br/>Health Check Integration]

    T2 --> T5[TASK-DB-005<br/>Initial Migration]
    T3 --> T5
    T3 --> T6[TASK-DB-006<br/>CRUD Operations]
    T4 --> T6
    T4 --> T8

    T6 --> T7[TASK-DB-007<br/>Users API Router]

    style T2 fill:#cfc,stroke:#090
    style T3 fill:#cfc,stroke:#090
    style T4 fill:#cfc,stroke:#090
    style T5 fill:#cfc,stroke:#090
    style T6 fill:#cfc,stroke:#090
    style T8 fill:#cfc,stroke:#090
```

_Tasks with green background can run in parallel within their wave._

## Execution Strategy

### Wave 1: Foundation (1 task)
| Task | Name | Complexity | Mode |
|------|------|-----------|------|
| TASK-DB-001 | Create database infrastructure | 5 | task-work |

### Wave 2: Core Components (3 tasks, parallel)
| Task | Name | Complexity | Mode |
|------|------|-----------|------|
| TASK-DB-002 | Set up Alembic migrations | 4 | task-work |
| TASK-DB-003 | Create user model and schemas | 4 | task-work |
| TASK-DB-004 | Set up database test infrastructure | 5 | task-work |

### Wave 3: Feature Implementation (3 tasks, parallel)
| Task | Name | Complexity | Mode |
|------|------|-----------|------|
| TASK-DB-005 | Create initial migration | 2 | direct |
| TASK-DB-006 | Implement CRUD operations | 5 | task-work |
| TASK-DB-008 | Integrate database health check | 4 | task-work |

### Wave 4: API Layer (1 task)
| Task | Name | Complexity | Mode |
|------|------|-----------|------|
| TASK-DB-007 | Implement users API router | 6 | task-work |

## §4: Integration Contracts

### Contract: DATABASE_URL
- **Producer task:** TASK-DB-001 (Create database infrastructure)
- **Consumer task(s):** TASK-DB-003 (User model - imports Base), TASK-DB-008 (Health check - uses get_db)
- **Artifact type:** environment variable + Settings field
- **Format constraint:** `postgresql+asyncpg://user:pass@host:port/dbname` (asyncpg dialect required by SQLAlchemy async `create_async_engine`)
- **Validation method:** Coach verifies `database_url` field in Settings uses `postgresql+asyncpg://` prefix; `.env.example` contains correct format

### Contract: Base (DeclarativeBase)
- **Producer task:** TASK-DB-001 (Creates `src/db/base.py` with `Base` class)
- **Consumer task(s):** TASK-DB-003 (User model inherits from Base), TASK-DB-002 (Alembic uses `Base.metadata`)
- **Artifact type:** Python class import
- **Format constraint:** `from src.db.base import Base` - must be a SQLAlchemy `DeclarativeBase` subclass with common column mixins
- **Validation method:** Coach verifies User model imports and inherits from Base; Alembic env.py references `Base.metadata`

### Contract: get_db (AsyncSession dependency)
- **Producer task:** TASK-DB-001 (Creates `src/db/dependencies.py` with `get_db()`)
- **Consumer task(s):** TASK-DB-007 (Router endpoints use `Depends(get_db)`), TASK-DB-008 (Health check uses `Depends(get_db)`)
- **Artifact type:** FastAPI dependency function
- **Format constraint:** `async def get_db() -> AsyncGenerator[AsyncSession, None]` - yields `AsyncSession` from `async_sessionmaker`
- **Validation method:** Coach verifies router and health check inject `db: AsyncSession = Depends(get_db)`

## New Files Created

```
src/
  db/
    __init__.py
    base.py              # DeclarativeBase, common columns
    session.py           # Engine, sessionmaker, pool config
    dependencies.py      # get_db() FastAPI dependency
  users/
    __init__.py
    models.py            # User SQLAlchemy model
    schemas.py           # UserCreate, UserUpdate, UserPublic, UserList
    crud.py              # Functional CRUD operations
    router.py            # API endpoints
    exceptions.py        # UserNotFoundError, UserAlreadyExistsError
alembic/
  env.py                 # Async migration runner
  script.py.mako         # Migration template
  versions/
    001_create_users_table.py
alembic.ini
tests/
  users/
    __init__.py
    test_router.py       # API integration tests
    test_crud.py         # CRUD unit tests
    test_schemas.py      # Schema validation tests
```

## Files Modified

| File | Change |
|------|--------|
| `src/core/config.py` | Add database settings (url, pool_size, etc.) |
| `src/main.py` | Engine init/dispose in lifespan; register users router |
| `src/health/schemas.py` | Add `database` field to HealthResponse |
| `src/health/router.py` | Add DB probe with get_db dependency |
| `tests/conftest.py` | Add database fixtures, dependency overrides |
| `requirements/base.txt` | Add `email-validator` |
| `requirements/dev.txt` | Add `aiosqlite>=0.19.0` |
| `.env.example` | Update DATABASE_URL format |

## New Dependencies

| Package | Purpose | File |
|---------|---------|------|
| `email-validator` | Pydantic EmailStr validation | `requirements/base.txt` |
| `aiosqlite>=0.19.0` | SQLite async driver for tests | `requirements/dev.txt` |

Already declared (no changes needed): `sqlalchemy>=2.0.0`, `asyncpg>=0.29.0`, `alembic>=1.12.0`

## Risk Factors

1. **mypy strict mode** - SQLAlchemy async typing can be challenging. Use `Mapped[T]` annotation style throughout.
2. **SQLite vs PostgreSQL in tests** - Minor behavioral differences. Acceptable for this scope since the User model is simple.
3. **Alembic async env.py** - Must be written manually (not auto-generated). Follow SQLAlchemy docs carefully.
4. **Health endpoint regression** - Modifying existing endpoint requires careful test updates.
