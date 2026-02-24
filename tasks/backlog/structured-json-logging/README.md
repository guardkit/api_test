# Feature: Structured JSON Logging

## Problem Statement

The application currently has zero logging infrastructure. There are no logging imports, no configuration, and no structured output anywhere in the codebase. This makes production observability, debugging, and request tracing impossible.

## Solution Approach

Implement structured JSON logging using `structlog` with the following components:

1. **Logging Settings** - Add `log_level` and `log_format` to `core/config.py` with environment-driven defaults
2. **structlog Configuration** - Create `src/core/logging.py` with processor pipeline, JSON rendering in production, colored console in development
3. **Correlation ID Middleware** - Generate UUID4 per request, propagate via `contextvars`, inject into all log records
4. **Request/Response Logging Middleware** - Log method, path, status code, duration for every request
5. **Health Endpoint Integration** - Expose current log level and format in `/health` response

## Technology Choice

**structlog** was selected over `python-json-logger` and `loguru` because:
- Native `contextvars` support for correlation IDs in async code
- Processor pipeline for extensible formatting
- Wraps stdlib logging so uvicorn/SQLAlchemy logs also get structured output
- First-class environment-conditional rendering (JSON in prod, colored in dev)

## Subtask Summary

| Task | Description | Complexity | Mode |
|------|------------|-----------|------|
| TASK-LOG-001 | Add logging settings to core config | 2/10 | direct |
| TASK-LOG-002 | Create structlog configuration module | 5/10 | task-work |
| TASK-LOG-003 | Create correlation ID + request logging middleware | 6/10 | task-work |
| TASK-LOG-004 | Integrate logging config with health endpoint | 3/10 | direct |
| TASK-LOG-005 | Add comprehensive tests for logging components | 5/10 | task-work |

## Execution Strategy

- **Wave 1**: TASK-LOG-001 (foundation config)
- **Wave 2**: TASK-LOG-002 (structlog setup, depends on config)
- **Wave 3**: TASK-LOG-003 + TASK-LOG-004 (parallel - middleware and health, both depend on logging module)
- **Wave 4**: TASK-LOG-005 (tests for all components)

## Original Review

TASK-REV-E19E - Plan: Implement structured JSON logging
