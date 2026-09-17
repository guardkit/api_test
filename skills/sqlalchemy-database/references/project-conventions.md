# SQLAlchemy project conventions

Reviewed from api_test revision 8aed8955b6797d87b5eb234c49c092138a07505d on 17 September 2026.

## Sources inspected

- .claude/CLAUDE.md
- .claude/agents/fastapi-database-specialist.md and fastapi-database-specialist-ext.md
- .claude/agents/fastapi-testing-specialist.md and fastapi-testing-specialist-ext.md
- .claude/agents/fastapi-specialist.md and fastapi-specialist-ext.md
- docs/architecture/adr-004-sqlalchemy-async-orm.md
- docs/architecture/adr-006-dependency-injection-for-db-sessions.md
- pyproject.toml, requirements/base.txt, and requirements/dev.txt
- src/db/base.py, src/db/session.py, and src/db/dependencies.py
- src/users/models.py, src/users/crud.py, and their tests
- alembic/env.py, tracked revisions, tests/test_alembic.py, and migration tests
- .guardkit/config.yaml, qa/run-suite.sh, tests/__init__.py, tests/conftest.py, and tests/suite_database.py

## Current implementation

- Runtime dependencies declare SQLAlchemy 2.x, Alembic, and asyncpg. Development dependencies include pytest, pytest-asyncio, pytest-forked, httpx, and aiosqlite.
- src/db/session.py creates a lazy async engine and async_sessionmaker(..., expire_on_commit=False). Its context managers close sessions but do not commit or roll back for callers.
- src/db/dependencies.py owns the FastAPI dependency that tests override.
- Models derive from DeclarativeBase, which carries the repository's naming convention.
- Current user mutation functions own their commits. Creation and deletion roll back caught write failures. Tests under TestTheWritesOutliveTheirSession verify that committed writes are visible through a second session.
- Read queries use SQLAlchemy 2.x statements. Existing code contains dialect-aware behavior because SQLite and PostgreSQL do not accept every expression or datetime comparison in the same way.
- Alembic reads the application metadata and DATABASE_URL, and uses an async engine for online migrations.

## Real database checks

- Merge-ready suite: qa/run-suite.sh
- Focused transaction and query feedback: .venv/bin/python -m pytest -q --forked tests/users/test_crud.py
- Focused fixture bootstrap behavior with Docker mocked: .venv/bin/python -m pytest -q tests/test_suite_database.py

qa/run-suite.sh starts PostgreSQL 16 on an automatically selected loopback port, exports its DATABASE_URL, and runs the tracked pytest suite with the repository's two ledgered deselections. The fixtures create a unique schema for each database-backed test and drop it afterward. A named but unreachable DATABASE_URL fails; it does not silently fall back.

Plain pytest imports tests/__init__.py, which asks tests/suite_database.py for a real PostgreSQL by default. API_TEST_TESTS_USE_SQLITE=1 explicitly selects SQLite and prints that limitation. A SQLite result is useful for a deliberately narrow unit check, rather than acceptance of SQL, persistence, schema, or migration behavior.

For a schema task, supplement relevant tests with upgrade and downgrade checks against an isolated PostgreSQL database. The existing tests/test_alembic.py includes configuration and SQLite migration coverage, so it does not by itself prove PostgreSQL migration behavior.

## Corrections to legacy specialist text

- The legacy blanket rule that CRUD must never commit is wrong for this revision. The request dependency does not commit, and cross-session tests require mutation functions to persist their writes.
- The legacy blanket preference for in-memory SQLite is wrong for integration evidence in this repository.
- expire_on_commit=False is an established session setting, but it does not replace explicit transaction ownership, rollback, or cross-session verification.
- Do not add a migration for every database-adjacent task. Add one only when the persisted schema changes.
