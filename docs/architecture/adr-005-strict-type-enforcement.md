# ADR-005: Strict Type Enforcement

## Status
Accepted

## Context
The repository serves as a production-ready FastAPI backend template where type safety is a core principle. As the codebase grows with multiple feature modules (users, search, stats, uptime, etc.), maintaining consistency in type annotations prevents runtime errors and improves developer experience during refactoring.

## Decision
Enforce strict type annotations across all Python modules. Every function signature, class attribute, and variable assignment must include explicit type hints. This is enforced via `[tool.mypy] strict = true` in `pyproject.toml` (verified present); there is no CI pipeline in this repository today.

## Consequences
- **Makes**: Static analysis reliable, IDE autocompletion accurate, and refactoring safer.
- **Forbids**: Implicit `Any` types, untyped function arguments, and unannotated return values.
- **Requires**: Developers to annotate all new code and existing code during feature development.

## Evidence
- `pyproject.toml` configures mypy in strict mode.
- `src/users/crud.py` and `src/users/router.py` demonstrate full annotation of function signatures.
- `src/core/config.py` uses Pydantic models with explicit type definitions.
- `src/db/session.py` annotates database session dependencies.
- All feature modules (search, stats, time, uptime, version, whoami) follow this pattern in their `router.py` and `schemas.py` files.
