---
id: TASK-LOG-005
title: Add comprehensive tests for logging components
task_type: testing
parent_review: TASK-REV-E19E
feature_id: FEAT-LOG
status: pending
priority: high
complexity: 5
wave: 4
implementation_mode: task-work
dependencies:
  - TASK-LOG-003
  - TASK-LOG-004
estimated_minutes: 60
tags: [logging, testing]
---

# Task: Add comprehensive tests for logging components

## Description

Create comprehensive tests for all logging infrastructure components: configuration, structlog setup, correlation ID middleware, request logging middleware, and health endpoint integration.

## Test Files to Create

### `tests/test_logging.py` (new)
- Test `setup_logging()` configures structlog correctly
- Test `get_logger()` returns bound logger
- Test JSON output format when `log_format == "json"`
- Test console output format when `log_format == "console"`
- Test log level filtering (DEBUG messages filtered at INFO level)
- Test correlation ID appears in log output when bound

### `tests/test_middleware.py` (update existing)
Add tests for new middleware:
- Test `CorrelationIDMiddleware` generates UUID4 in `X-Correlation-ID` response header
- Test `CorrelationIDMiddleware` respects incoming `X-Correlation-ID` header
- Test `CorrelationIDMiddleware` binds correlation ID to structlog context
- Test `RequestLoggingMiddleware` logs request start and completion
- Test `RequestLoggingMiddleware` includes duration_ms in completion log
- Test `RequestLoggingMiddleware` includes correlation_id in logs
- Test middleware order (correlation ID available in request logs)

### `tests/health/test_router.py` (update existing)
- Test `GET /health` includes `log_level` in response
- Test `GET /health` includes `log_format` in response

### `tests/health/test_schemas.py` (update existing)
- Test `HealthResponse` schema includes `log_level` field
- Test `HealthResponse` schema includes `log_format` field
- Test OpenAPI schema reflects new fields

## Acceptance Criteria

- [ ] All logging configuration tests pass
- [ ] All correlation ID middleware tests pass
- [ ] All request logging middleware tests pass
- [ ] Updated health endpoint tests pass
- [ ] Code coverage >= 80% for new logging code
- [ ] All existing tests continue to pass (no regressions)

## Implementation Notes

- Use `caplog` or `capsys` pytest fixtures to capture log output for assertions
- For structlog, use `structlog.testing.capture_logs()` context manager
- For middleware tests, use the existing `client` and `async_client` fixtures from `conftest.py`
- Follow existing test patterns: class-based organization, docstrings on all test methods
