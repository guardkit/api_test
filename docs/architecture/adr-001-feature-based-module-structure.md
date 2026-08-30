# ADR-001: Feature-Based Module Organization

## Status
Accepted

## Context
As the project grows, organizing code by file type (e.g., all routers in one folder, all models in another) creates cognitive load. Developers must traverse the entire tree to understand a single domain. The repository needs a structure that keeps related logic together to improve maintainability and developer velocity.

## Decision
Organize code by domain modules rather than by file type. Each feature gets a dedicated directory containing its own router, schemas, models, and business logic.

**The rule**: A new feature must reside in `src/{feature_name}/` with its own:
- `router.py` (API endpoints) — required in every feature
- `schemas.py` (Pydantic models) — required in every feature
- `models.py` (SQLAlchemy models) — required only where the feature stores data in the database
- `crud.py` (Database operations) — required only where the feature stores data in the database
- `service.py` (Business logic) — allowed, not required
- `dependencies.py` (Feature-specific dependencies) — allowed, not required
- `constants.py` (Feature constants) — allowed, not required
- `exceptions.py` (Custom exceptions) — allowed, not required
- `config.py` (Feature configuration) — allowed, not required
- `utils.py` (Helper functions) — allowed, not required

No feature currently has a `service.py`; a business-logic file is allowed, not required (ruled 2026-08-30) — a rule the code cannot pass today would make the conformance report noise from day one.

## Consequences

**What it makes easy**:
- Locating all code related to a single domain (e.g., "users") in one place.
- Adding new features without touching unrelated modules.
- Testing features in isolation.

**What it forbids**:
- Creating a global `models/` directory containing all ORM models.
- Creating a global `schemas/` directory for all Pydantic models.
- Cross-feature coupling where one module imports internals from another's private files.

**The sanctioned exception**: the shared base-class file `src/schemas.py` (`BaseSchema` and friends, inherited by feature schemas) is allowed under the no-global-schemas rule. What stays forbidden is a global directory collecting feature-specific models.

## Evidence
- `src/users/` contains `router.py`, `schemas.py`, `models.py`, `crud.py`, and `exceptions.py`.
- `src/search/` contains `router.py` and `schemas.py`.
- `src/health/` contains `router.py` and `schemas.py`.
- `src/uptime/` contains `router.py` and `schemas.py`.
- `src/version/` contains `router.py`, `schemas.py`, and `utils.py`.
- `src/whoami/` contains `router.py` and `schemas.py`.
- `src/time/` contains `router.py` and `schemas.py`.
- `src/stats/` contains `router.py`.