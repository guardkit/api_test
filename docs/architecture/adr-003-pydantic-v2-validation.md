# ADR-003: Use Pydantic v2 models for all request and response validation

## Status
Accepted — this pattern is already implemented across the codebase.

## Context
The repository is built on FastAPI, which relies on Pydantic for data validation and serialization. As the project scales, inconsistent validation patterns lead to runtime errors and difficult-to-debug API contracts. We need a unified approach to ensure type safety and validation consistency across all feature modules.

## Decision
All request and response data must be validated using Pydantic v2 models. Specifically:
- Every API endpoint must define explicit Pydantic models for input (request bodies, query parameters) and output (response bodies).
- Models must be defined in the `schemas.py` file within each feature module.
- No raw dictionaries or untyped objects should be returned from routers.
- Pydantic's strict mode and type annotations must be used to enforce contract adherence.

## Consequences
- **What it makes easy**: Automatic documentation generation via OpenAPI, runtime validation error messages, and IDE type completion.
- **What it forbids**: Returning raw dictionaries from endpoints, bypassing validation via `dict()` conversions without re-validation, and using untyped `Any` for request/response payloads.
- **Maintenance**: Requires updating schemas when API contracts change, but ensures breaking changes are caught at the type-checking stage.

## Evidence
- `src/users/schemas.py` defines Pydantic models for user data.
- `src/search/schemas.py` defines search request/response models.
- `src/time/schemas.py` defines time-related response models.
- `src/uptime/schemas.py` defines uptime response models.
- `src/version/schemas.py` defines version response models.
- `src/whoami/schemas.py` defines whoami response models.
- `src/health/schemas.py` defines health check response models.
- All router files (`src/*/router.py`) use these schemas for type annotations in endpoint signatures.