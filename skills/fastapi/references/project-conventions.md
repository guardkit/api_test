# FastAPI project conventions

Reviewed from api_test revision 8aed8955b6797d87b5eb234c49c092138a07505d on 17 September 2026.

## Sources inspected

- .claude/CLAUDE.md
- .claude/agents/fastapi-specialist.md and fastapi-specialist-ext.md
- .claude/agents/fastapi-testing-specialist.md and fastapi-testing-specialist-ext.md
- .claude/agents/fastapi-database-specialist.md and fastapi-database-specialist-ext.md
- docs/architecture/adr-001-feature-based-module-structure.md
- docs/architecture/adr-002-async-first-io.md
- docs/architecture/adr-003-pydantic-v2-validation.md
- docs/architecture/adr-004-sqlalchemy-async-orm.md
- docs/architecture/adr-006-dependency-injection-for-db-sessions.md
- pyproject.toml, .guardkit/config.yaml, and qa/run-suite.sh
- src/main.py, src/db/, representative feature routers, schemas, exceptions, and CRUD modules
- tests/conftest.py, tests/__init__.py, and tests/suite_database.py

## Current patterns

- src/main.py builds the shared FastAPI application and registers feature routers with app.include_router(...).
- Feature routers use APIRouter. Database-backed routes depend on src.db.dependencies.get_db, and tests override that exact function object.
- Feature schemas use Pydantic v2 APIs including ConfigDict, field_validator, model_validator, and model_dump.
- Feature exception classes subclass HTTPException for expected client-visible failures. Routers also map database failures to their declared responses where appropriate.
- Async route tests use httpx.AsyncClient with ASGITransport(app=app). The project has asyncio_mode = "auto", so async tests do not require a marker merely to run.
- The test fixtures are function-scoped and remove app.dependency_overrides after use.

## Commands already declared by the project

- Merge-ready suite: qa/run-suite.sh
- Focused route feedback in the worktree environment: .venv/bin/python -m pytest -q --forked tests/users/test_router.py

The full suite is the repository's declared toolchain.test and starts an isolated PostgreSQL 16 container on a free loopback port. Run it only in the authorized application sandbox. Plain pytest also selects a real PostgreSQL through tests/__init__.py and tests/suite_database.py unless SQLite is explicitly requested; read the database skill before interpreting a database-backed result.

## Corrections to legacy specialist text

- Do not copy the old AsyncClient(app=app, ...) examples; this repository uses ASGITransport.
- Do not make in-memory SQLite the default evidence for database behavior. The suite of record uses PostgreSQL because dialect differences have hidden defects here.
- Do not require @pytest.mark.asyncio everywhere; pytest is configured with automatic async mode.
- Do not invent authentication failures or factory fixtures for endpoints that have neither. Select cases from the actual route contract.
- Do not impose a generic service or repository layer. The feature ADR permits optional service files and the existing feature layout is the authority.
