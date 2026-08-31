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

**Amendment, 2026-08-31 — which files are public and which are private**

The forbidden list above draws a line between one feature's private files and everything else, but it never says which files are which. This says which.

A feature's **public read interface** is its `crud.py` — the functions in it whose names do not start with an underscore — and its `schemas.py`, the shapes those functions return. Another feature may import those two files.

A feature's **private files** are `models.py`, `service.py`, `router.py`, `dependencies.py`, and anything whose name starts with an underscore. Another feature may not import those.

The public functions must return schemas or plain data, never ORM model instances. A public function that hands back a model instance leaks the model through the interface, the caller ends up importing the model anyway, and the boundary is only nominal. This last point is written guidance for people: the checker does not verify it. The checker looks at which files an import names, not at what a function returns.

What taught this: the first build run with these rules enforced hit a request that could not be satisfied — an analytics feature had to read user data — which showed the record forbade the import without ever naming a legal way to do it.

## Evidence
- `src/users/` contains `router.py`, `schemas.py`, `models.py`, `crud.py`, and `exceptions.py`.
- `src/search/` contains `router.py` and `schemas.py`.
- `src/health/` contains `router.py` and `schemas.py`.
- `src/uptime/` contains `router.py` and `schemas.py`.
- `src/version/` contains `router.py`, `schemas.py`, and `utils.py`.
- `src/whoami/` contains `router.py` and `schemas.py`.
- `src/time/` contains `router.py` and `schemas.py`.
- `src/stats/` contains `router.py`.
