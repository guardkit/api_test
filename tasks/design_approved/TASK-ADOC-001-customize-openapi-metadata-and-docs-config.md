---
complexity: 3
dependencies: []
feature_id: FEAT-7158
id: TASK-ADOC-001
implementation_mode: task-work
parent_review: TASK-REV-7158
priority: high
status: design_approved
tags:
- documentation
- openapi
- swagger
- redoc
task_type: feature
test_results:
  coverage: null
  last_run: null
  status: pending
title: Customize OpenAPI metadata and Swagger/ReDoc configuration
wave: 1
---

# Task: Customize OpenAPI metadata and Swagger/ReDoc configuration

## Description

Enrich the FastAPI application initialization in `src/main.py` with comprehensive OpenAPI metadata and configure Swagger UI and ReDoc documentation endpoints. This provides the foundation for all API documentation by adding rich metadata visible in both documentation UIs.

## Current State

The `FastAPI()` constructor in `src/main.py` currently has only:
- `title=settings.app_name` (just "api")
- `version="0.1.0"`
- `debug=settings.debug`

No description, contact info, license, terms, or tag descriptions are configured.

## Implementation Details

### 1. Add OpenAPI metadata to FastAPI constructor

Add the following parameters to the `FastAPI()` call in `src/main.py`:
- `description`: A multi-line markdown description of the API
- `summary`: A short one-line summary
- `contact`: Dict with `name`, `url`, `email`
- `license_info`: Dict with `name` and `url` (e.g., MIT)
- `terms_of_service`: URL string
- `openapi_tags`: List of tag metadata dicts with `name`, `description`, and optional `externalDocs`

### 2. Add settings for documentation metadata

Add configurable settings to `src/core/config.py`:
- `app_description`: Markdown API description
- `app_summary`: Short summary line
- `app_contact_name`, `app_contact_email`, `app_contact_url`: Contact info

### 3. Configure Swagger UI and ReDoc

Ensure FastAPI serves:
- Swagger UI at `/docs` (default, but customize `swagger_ui_parameters` for expanded operations, try-it-out enabled)
- ReDoc at `/redoc` (default)
- OpenAPI schema at `/openapi.json`

Pass `swagger_ui_parameters={"defaultModelsExpandDepth": -1, "tryItOutEnabled": True}` to the `FastAPI()` constructor for enhanced Swagger UI defaults.

## Acceptance Criteria

- [ ] `FastAPI()` constructor includes `description`, `summary`, `contact`, `license_info`, and `openapi_tags` parameters
- [ ] Settings class includes new documentation-related fields with sensible defaults
- [ ] `GET /docs` renders Swagger UI with full metadata visible
- [ ] `GET /redoc` renders ReDoc with full metadata visible
- [ ] `GET /openapi.json` returns schema with all metadata fields populated
- [ ] OpenAPI tags include at least "health" with a description
- [ ] `swagger_ui_parameters` configures enhanced defaults
- [ ] All existing tests continue to pass
- [ ] New tests verify OpenAPI schema contains expected metadata fields

## Test Requirements

- [ ] Test that `app.openapi()` schema contains `info.description`
- [ ] Test that `app.openapi()` schema contains `info.contact`
- [ ] Test that `app.openapi()` schema contains `info.license`
- [ ] Test that `GET /openapi.json` returns valid schema with tags
- [ ] Test that `swagger_ui_parameters` are set on the app

## Implementation Notes

Use the version from `settings.app_version` rather than hardcoding "0.1.0" in the FastAPI constructor. This also fixes a minor inconsistency in the current code.