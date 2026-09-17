---
name: fastapi
description: Extend or review this project's FastAPI routes, dependency injection, Pydantic contracts, error handling, and API tests while preserving its established application wiring.
---

# FastAPI

Use this skill for work that changes or assesses the HTTP application. Trace the relevant feature from its router registration in src/main.py through its router, schemas, dependencies, database calls, and tests. Read [the project conventions](references/project-conventions.md) before changing those paths or choosing checks.

## Work with the existing application

- Keep code grouped by feature under src/<feature>/. A feature router and schemas are required; add models, CRUD, services, or feature dependencies only when the task needs them.
- Keep I/O asynchronous. Do not call blocking database, HTTP, or file APIs on the event loop.
- Inject database sessions with the existing src.db.dependencies.get_db dependency. Importing a different provider breaks the test override used by this application.
- Register every application router in src/main.py. Verify the complete route path from both its router prefix and decorator path. Preserve the repository's redirect_slashes=False choices where present.
- Express request and response contracts with typed Pydantic v2 schemas in the feature's schemas.py. Use an explicit response_model for structured responses and ConfigDict(from_attributes=True) when a response is built from ORM objects.
- Preserve established public status codes and response shapes. Translate expected domain conditions with the feature's exception types and translate operational failures only at the boundary that owns the HTTP response. Do not expose credentials or internal tracebacks.
- Follow the requested change and inspect related behavior before adding abstractions. A skill does not authorize unrelated helpers, scaffolding, schemas, migrations, dependencies, or endpoint behavior.

## Verify through the application

- Exercise the route through the FastAPI app, rather than only calling its function. Reuse the async_client and override_get_db fixtures in tests/conftest.py when database behavior is involved.
- Cover the success contract and relevant validation, missing-resource, conflict, and operational-error cases. Assert response data as well as status codes.
- Let fixtures remove dependency overrides and dispose database resources. Do not leave global app state behind.
- Use the declared suite qa/run-suite.sh for the merge-ready result. A focused pytest path can give quick feedback, but does not replace that suite. Database-backed checks must follow the real-database guidance in the sqlalchemy-database skill.

Do not copy Claude agent metadata or generic examples into application code. The source notes identify which older recommendations were corrected for this repository.
