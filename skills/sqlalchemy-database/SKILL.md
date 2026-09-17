---
name: sqlalchemy-database
description: Extend or review this project's async SQLAlchemy models, sessions, queries, transactions, Alembic migrations, and real-database tests.
---

# SQLAlchemy database

Use this skill when work touches persistence, transaction behavior, database queries, ORM models, or Alembic. Read [the project conventions](references/project-conventions.md) before deciding where a transaction belongs or what counts as database evidence.

## Preserve async database boundaries

- Use SQLAlchemy 2.x async APIs: AsyncSession, select(), execute(), and mapped SQLAlchemy 2.x models based on src.db.base.DeclarativeBase.
- Obtain request sessions through src.db.dependencies.get_db. Do not create engines or sessions inside feature routers or business logic.
- Make transaction ownership explicit. In this repository, the session dependency closes but does not commit, and existing mutation functions in src/users/crud.py commit so writes survive the request. Do not replace that behavior with generic flush-only advice unless the task deliberately changes the ownership boundary and proves every caller.
- Use flush() when generated or constrained database state must be observed before commit, refresh() when returned ORM state must be loaded, and rollback() after a failed write before reusing or closing the session. Catch only exceptions that the owning layer can translate meaningfully.
- Write typed, parameterized SQLAlchemy expressions. Preserve domain filters and ordering by tracing neighboring queries, models, and tests. Account for PostgreSQL semantics; a SQLite-only pass is insufficient for database behavior.
- Avoid implicit lazy loading in async code. Load relationships deliberately when a task introduces or uses them.

## Change schemas deliberately

- Add an Alembic revision only when the persisted schema changes. Query, route, and response-only work does not need a migration.
- Keep models, Alembic metadata, revision ancestry, upgrade, and downgrade behavior consistent. Review generated revisions before use; do not treat generation as proof.
- For a schema change, verify upgrade behavior and the intended rollback behavior against an isolated database as well as running relevant application tests.

## Require meaningful database evidence

- Use this repository's PostgreSQL-backed suite of record for integration evidence. Mocks can prove error translation or call shape; they cannot prove SQL, constraints, transactions, migrations, or dialect behavior.
- Keep each test isolated. The existing fixtures create a unique PostgreSQL schema per test and clean it up. Use in-memory SQLite only when explicitly requested for a limited unit check.
- Include a cross-session assertion when persistence is part of the contract. A read through the same transaction can pass even when a write was never committed.
- Use qa/run-suite.sh for the merge-ready result. Focused pytest paths are preliminary checks and use the same real-database selection unless SQLite is explicitly selected.

This skill supplies guidance only. It does not authorize a schema, migration, dependency, helper, test scaffold, or application change outside the task.
