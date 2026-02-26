# Feature: PostgreSQL Database Integration

**Feature ID**: FEAT-DB
**Review**: [TASK-REV-4B7D](../TASK-REV-4B7D-plan-postgresql-database-integration.md)
**Status**: Planned
**Complexity**: 6/10
**Tasks**: 8

## Summary

Add PostgreSQL database integration using SQLAlchemy async with connection pooling, health check integration, and a sample users table with CRUD endpoints.

## Tasks

| Wave | Task | Name | Complexity | Mode | Status |
|------|------|------|-----------|------|--------|
| 1 | TASK-DB-001 | Create database infrastructure | 5 | task-work | pending |
| 2 | TASK-DB-002 | Set up Alembic migrations | 4 | task-work | pending |
| 2 | TASK-DB-003 | Create user model and schemas | 4 | task-work | pending |
| 2 | TASK-DB-004 | Set up database test infrastructure | 5 | task-work | pending |
| 3 | TASK-DB-005 | Create initial migration | 2 | direct | pending |
| 3 | TASK-DB-006 | Implement CRUD operations | 5 | task-work | pending |
| 3 | TASK-DB-008 | Integrate database health check | 4 | task-work | pending |
| 4 | TASK-DB-007 | Implement users API router | 6 | task-work | pending |

## Quick Start

```bash
# Start with Wave 1
/task-work TASK-DB-001

# After Wave 1, run Wave 2 tasks (can be parallel)
/task-work TASK-DB-002
/task-work TASK-DB-003
/task-work TASK-DB-004

# After Wave 2, run Wave 3 tasks (can be parallel)
/task-work TASK-DB-005
/task-work TASK-DB-006
/task-work TASK-DB-008

# Finally, Wave 4
/task-work TASK-DB-007
```

## Key Decisions

- **Functional CRUD** over generic base class (no premature abstraction)
- **SQLite in-memory** for tests (no Docker required)
- **Inline health probe** over separate liveness/readiness (upgradeable later)
- **Standard Alembic** at project root (not nested under src/db/)

## See Also

- [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md) - Detailed architecture, diagrams, and contracts
