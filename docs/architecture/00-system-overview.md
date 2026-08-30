# System Overview

## Service Purpose

api_test is a FastAPI-based backend service designed as a production-ready template. It implements feature-based organization with async-first patterns, emphasizing scalability and maintainability through strict type safety and dependency injection.

## Architectural Layers

The service is structured into distinct layers, each with specific responsibilities:

- **API Layer (`router.py`)**: Defines HTTP endpoints, handles request/response routing, and manages dependency injection at the route level.
- **Schema Layer (`schemas.py`)**: Uses Pydantic models for data validation, request/response serialization, and type definitions.
- **Model Layer (`models.py`)**: Contains SQLAlchemy ORM models, database table definitions, and relationship constraints.
- **CRUD Layer (`crud.py`)**: Implements database operations (Create, Read, Update, Delete) using the repository pattern.
- **Service Layer (`service.py`)**: Orchestrates business logic, complex operations, and cross-entity coordination.
- **Dependency Layer (`dependencies.py`)**: Provides reusable functions for authentication, database session management, and request validation.

## Feature Organization

Each domain feature follows a consistent file structure within `src/`:

Required in every feature:

- `router.py`: API endpoints
- `schemas.py`: Pydantic models

Required only where the feature stores data in the database:

- `models.py`: SQLAlchemy models
- `crud.py`: Database operations

Allowed, but not required, in any feature:

- `service.py`: Business logic
- `dependencies.py`: Feature-specific dependencies
- `constants.py`: Feature constants
- `exceptions.py`: Custom exceptions
- `config.py`: Feature configuration
- `utils.py`: Helper functions

## Data Persistence

The architecture supports two database layers:

- **Primary Database**: Managed via SQLAlchemy ORM with Alembic for migrations, optimized for structured domain data.
- **Caching/Ephemeral Storage**: Utilized for transient data where persistence is not required, reducing load on the primary database.

## Quality and Validation

The system maintains quality through three primary surfaces:

- **Automated Testing**: Pytest with async support (`pytest-asyncio`) and coverage reporting (`pytest-cov`), targeting 80% line coverage.
- **Live-Request Twins**: Integration tests that mirror production request patterns to validate endpoint behavior.
- **Quality Gates**: Ruff linting and strict MyPy type checking, both configured in `pyproject.toml` and run locally. There is no pre-commit configuration and no CI workflow in this repository.