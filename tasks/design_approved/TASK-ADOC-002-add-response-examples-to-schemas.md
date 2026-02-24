---
complexity: 3
dependencies:
- TASK-ADOC-001
feature_id: FEAT-7158
id: TASK-ADOC-002
implementation_mode: task-work
parent_review: TASK-REV-7158
priority: high
status: design_approved
tags:
- documentation
- pydantic
- schemas
- examples
task_type: feature
test_results:
  coverage: null
  last_run: null
  status: pending
title: Add response examples to Pydantic schemas
wave: 2
---

# Task: Add response examples to Pydantic schemas

## Description

Enhance existing Pydantic response schemas with `json_schema_extra` examples that appear in Swagger UI and ReDoc documentation. This uses Pydantic v2's native `model_config` pattern for embedding OpenAPI response examples directly in schema definitions.

## Current State

`src/health/schemas.py` defines `HealthResponse` with bare fields (`status: str`, `version: str`) and no examples or field descriptions.

## Implementation Details

### 1. Add examples to HealthResponse

Update `HealthResponse` in `src/health/schemas.py` to use Pydantic v2 patterns:
- Add `Field(description=...)` to each field for field-level documentation
- Add `model_config = ConfigDict(json_schema_extra={"examples": [...]})` for response examples

```python
from pydantic import BaseModel, ConfigDict, Field

class HealthResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"status": "ok", "version": "0.1.0"},
            ]
        }
    )

    status: str = Field(description="Service health status")
    version: str = Field(description="API version string")
```

### 2. Create a base schema pattern

Create `src/schemas.py` (shared base) with a `BaseSchema` class that establishes the pattern for all future schemas to follow. This is lightweight - just sets the convention.

### 3. Add OpenAPI response descriptions to router

Update `src/health/router.py` to include `responses` parameter on the endpoint decorator with status code descriptions:

```python
@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Check service health",
    description="Returns the current health status and version of the API service.",
    responses={
        200: {"description": "Service is healthy"},
    },
)
```

## Acceptance Criteria

- [ ] `HealthResponse` includes `json_schema_extra` with at least one example
- [ ] Each field in `HealthResponse` has a `description` via `Field()`
- [ ] Health endpoint has `summary` and `description` in decorator
- [ ] Health endpoint has `responses` dict with status code descriptions
- [ ] `GET /openapi.json` schema shows examples in the `HealthResponse` component
- [ ] Swagger UI "Try it out" shows example response
- [ ] ReDoc shows example response in documentation
- [ ] All existing tests continue to pass
- [ ] New tests verify schema examples are present in OpenAPI output

## Test Requirements

- [ ] Test that OpenAPI schema components contain examples for HealthResponse
- [ ] Test that OpenAPI paths contain response descriptions
- [ ] Test that Field descriptions appear in schema properties

## Implementation Notes

Use `ConfigDict` from pydantic (Pydantic v2 pattern), not the old `class Config` inner class. The project already uses Pydantic v2.