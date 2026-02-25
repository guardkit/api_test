---
id: TASK-LOG-003
title: Create correlation ID and request logging middleware
task_type: feature
parent_review: TASK-REV-E19E
feature_id: FEAT-LOG
status: pending
priority: high
complexity: 6
wave: 3
implementation_mode: task-work
dependencies:
  - TASK-LOG-002
estimated_minutes: 90
tags: [logging, middleware, correlation-id]
consumer_context:
  - task: TASK-LOG-002
    consumes: STRUCTLOG_LOGGER
    framework: "structlog bound logger via get_logger()"
    driver: "structlog"
    format_note: "Logger must be obtained via get_logger() from src.core.logging; correlation ID must be bound via structlog.contextvars.bind_contextvars()"
---

# Task: Create correlation ID and request logging middleware

## Description

Create two middleware components in `src/core/middleware.py`:

1. **CorrelationIDMiddleware** - Generates a UUID4 correlation ID per request, stores it in a `ContextVar`, binds it to structlog context, and adds it as `X-Correlation-ID` response header
2. **RequestLoggingMiddleware** - Logs request start (method, path, correlation_id) and request completion (method, path, status_code, duration_ms, correlation_id)

## Changes Required

### `src/core/middleware.py`
Add two new middleware classes alongside the existing `APIVersionHeaderMiddleware`:

**CorrelationIDMiddleware**:
- Check for incoming `X-Correlation-ID` header (use existing if present, generate UUID4 if not)
- Store correlation ID in a `ContextVar`
- Bind to structlog context via `structlog.contextvars.bind_contextvars(correlation_id=...)`
- Add `X-Correlation-ID` to response headers
- Clear contextvars after request completes

**RequestLoggingMiddleware**:
- Log at request start: `logger.info("request_started", method=..., path=..., client_ip=...)`
- Log at request end: `logger.info("request_completed", method=..., path=..., status_code=..., duration_ms=...)`
- Calculate duration using `time.perf_counter()`
- Skip logging for health check endpoint (configurable)

### `src/main.py`
- Register both new middleware (order matters: CorrelationID first, then RequestLogging)

## Acceptance Criteria

- [ ] `CorrelationIDMiddleware` generates UUID4 for each request
- [ ] Incoming `X-Correlation-ID` header is respected if present
- [ ] Correlation ID stored in `ContextVar` and accessible throughout request lifecycle
- [ ] Correlation ID bound to structlog context (appears in all log entries for that request)
- [ ] `X-Correlation-ID` header added to all responses
- [ ] `RequestLoggingMiddleware` logs request start and completion
- [ ] Request duration measured in milliseconds
- [ ] Both middleware registered in correct order in `main.py`
- [ ] Health endpoint (`/health`) logging is skippable

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify STRUCTLOG_LOGGER contract from TASK-LOG-002."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("STRUCTLOG_LOGGER")
def test_structlog_logger_available():
    """Verify structlog logger is obtainable via get_logger().

    Contract: Logger must be obtained via get_logger() from src.core.logging;
              correlation ID must be bindable via structlog.contextvars
    Producer: TASK-LOG-002
    """
    from src.core.logging import get_logger
    import structlog

    logger = get_logger("test")
    assert logger is not None, "get_logger() must return a logger instance"

    # Verify contextvars binding works
    structlog.contextvars.bind_contextvars(correlation_id="test-id")
    ctx = structlog.contextvars.get_contextvars()
    assert "correlation_id" in ctx, "contextvars binding must support correlation_id"
    structlog.contextvars.unbind_contextvars("correlation_id")
```

## Implementation Notes

- Use `contextvars.ContextVar` for the correlation ID (not thread-local)
- Use `structlog.contextvars.bind_contextvars()` / `unbind_contextvars()` for log context
- Middleware order in `main.py`: CorrelationID should wrap RequestLogging so that request logs include the correlation ID
- Consider using pure ASGI middleware (not `BaseHTTPMiddleware`) for better performance and to avoid body consumption issues, but `BaseHTTPMiddleware` is acceptable since we're not reading request bodies
