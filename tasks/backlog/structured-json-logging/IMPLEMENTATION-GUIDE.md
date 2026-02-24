# Implementation Guide: Structured JSON Logging

## Overview

This guide covers the implementation of structured JSON logging with request correlation IDs, request/response logging middleware, and configurable log levels per environment for the FastAPI application.

**Approach**: structlog + stdlib logging integration
**Total Tasks**: 5
**Estimated Effort**: 4-5 hours
**Overall Complexity**: 6/10

## Data Flow: Read/Write Paths

```mermaid
flowchart LR
    subgraph Writes["Write Paths"]
        W1["Settings.__init__()\n(load from env vars)"]
        W2["setup_logging()\n(configure structlog + stdlib)"]
        W3["CorrelationIDMiddleware\n(bind correlation_id per request)"]
        W4["RequestLoggingMiddleware\n(emit request start/complete logs)"]
    end

    subgraph Storage["Storage"]
        S1[("Settings\n(pydantic-settings)")]
        S2[("structlog pipeline\n(in-memory config)")]
        S3[("ContextVar\n(per-request correlation_id)")]
        S4[("Log Output\n(stdout/stderr JSON)")]
    end

    subgraph Reads["Read Paths"]
        R1["setup_logging()\nreads log_level, log_format"]
        R2["Middleware\ncalls get_logger()"]
        R3["health_check()\nreads log_level, log_format"]
        R4["Application code\ncalls get_logger()"]
    end

    W1 -->|"env vars → fields"| S1
    W2 -->|"structlog.configure()"| S2
    W3 -->|"bind_contextvars()"| S3
    W4 -->|"logger.info()"| S4

    S1 -->|"settings.log_level"| R1
    S2 -->|"get_logger()"| R2
    S1 -->|"settings.log_level/format"| R3
    S2 -->|"get_logger()"| R4
    S3 -->|"merge_contextvars"| S4
```

_All write paths have corresponding read paths. No disconnections detected._

## Integration Contracts

```mermaid
sequenceDiagram
    participant Env as Environment (.env)
    participant Cfg as Settings (config.py)
    participant Log as setup_logging() (logging.py)
    participant CID as CorrelationIDMiddleware
    participant RLog as RequestLoggingMiddleware
    participant Health as health_check()
    participant Out as Log Output (stdout)

    Env->>Cfg: LOG_LEVEL, LOG_FORMAT
    Note over Cfg: Stores as settings.log_level, settings.log_format

    Cfg->>Log: settings.log_level, settings.log_format
    Log->>Log: structlog.configure(processors=[...])
    Note over Log: Pipeline configured with JSON or console renderer

    Note over CID,RLog: Per-request flow:
    CID->>CID: Generate UUID4 or read X-Correlation-ID
    CID->>CID: bind_contextvars(correlation_id=...)

    RLog->>Out: logger.info("request_started", method, path)
    Note over Out: correlation_id injected via merge_contextvars

    RLog->>Out: logger.info("request_completed", status, duration_ms)

    Health->>Cfg: Read settings.log_level, settings.log_format
    Health-->>Health: Return in HealthResponse
```

_Data flows completely from environment through config, to logging setup, to middleware, to output. Health endpoint reads config directly._

## Task Dependencies

```mermaid
graph TD
    T1[TASK-LOG-001: Add logging settings to config]
    T2[TASK-LOG-002: Create structlog configuration]
    T3[TASK-LOG-003: Correlation ID + request logging middleware]
    T4[TASK-LOG-004: Integrate with health endpoint]
    T5[TASK-LOG-005: Comprehensive tests]

    T1 --> T2
    T2 --> T3
    T2 --> T4
    T3 --> T5
    T4 --> T5

    style T3 fill:#cfc,stroke:#090
    style T4 fill:#cfc,stroke:#090
```

_Tasks with green background (TASK-LOG-003 and TASK-LOG-004) can run in parallel in Wave 3._

## Execution Strategy

### Wave 1: Foundation Config
| Task | Description | Mode | Complexity |
|------|------------|------|-----------|
| TASK-LOG-001 | Add logging settings to core config | direct | 2/10 |

**Files touched**: `src/core/config.py`, `.env.example`, `requirements/base.txt`

### Wave 2: Logging Infrastructure
| Task | Description | Mode | Complexity |
|------|------------|------|-----------|
| TASK-LOG-002 | Create structlog configuration module | task-work | 5/10 |

**Files touched**: `src/core/logging.py` (new), `src/main.py`

### Wave 3: Middleware + Health (Parallel)
| Task | Description | Mode | Complexity |
|------|------------|------|-----------|
| TASK-LOG-003 | Correlation ID + request logging middleware | task-work | 6/10 |
| TASK-LOG-004 | Integrate with health endpoint | direct | 3/10 |

**TASK-LOG-003 files**: `src/core/middleware.py`, `src/main.py`
**TASK-LOG-004 files**: `src/health/schemas.py`, `src/health/router.py`
**No file conflicts** - safe for parallel execution.

### Wave 4: Testing
| Task | Description | Mode | Complexity |
|------|------------|------|-----------|
| TASK-LOG-005 | Comprehensive tests | task-work | 5/10 |

**Files touched**: `tests/test_logging.py` (new), `tests/test_middleware.py`, `tests/health/test_router.py`, `tests/health/test_schemas.py`

## Section 4: Integration Contracts

### Contract: LOGGING_SETTINGS
- **Producer task:** TASK-LOG-001
- **Consumer task(s):** TASK-LOG-002
- **Artifact type:** Python class fields (pydantic Settings)
- **Format constraint:** `settings.log_level` must be a valid Python logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL); `settings.log_format` must be "json" or "console"
- **Validation method:** Coach verifies Settings class has `log_level: str` and `log_format: str` fields with correct defaults; unit test asserts valid values

### Contract: STRUCTLOG_LOGGER
- **Producer task:** TASK-LOG-002
- **Consumer task(s):** TASK-LOG-003, TASK-LOG-004
- **Artifact type:** Python module functions (`src/core/logging.py`)
- **Format constraint:** `get_logger(name: str)` must return a structlog BoundLogger; `setup_logging()` must configure both structlog and stdlib logging; correlation ID must be bindable via `structlog.contextvars.bind_contextvars(correlation_id=...)`
- **Validation method:** Coach verifies `get_logger()` returns a structlog logger instance; seam test verifies contextvars binding works

## Architecture Notes

### structlog Processor Pipeline

```
Input → add_log_level → timestamper → merge_contextvars → add_caller_info → renderer
                                            ↑
                                   correlation_id from ContextVar
```

- **JSON renderer** (`structlog.processors.JSONRenderer`): Used when `log_format == "json"` (production)
- **Console renderer** (`structlog.dev.ConsoleRenderer`): Used when `log_format == "console"` (development)

### Middleware Registration Order

In `main.py`, middleware is applied in reverse order (last added = outermost):
```python
app.add_middleware(RequestLoggingMiddleware)    # Inner: logs with correlation ID
app.add_middleware(CorrelationIDMiddleware)     # Outer: sets up correlation ID first
app.add_middleware(APIVersionHeaderMiddleware)  # Existing: adds version header
```

### Correlation ID Flow

1. Request arrives → `CorrelationIDMiddleware` generates/extracts UUID
2. UUID stored in `ContextVar` and bound to structlog via `bind_contextvars()`
3. All subsequent log calls within this request automatically include `correlation_id`
4. Response gets `X-Correlation-ID` header
5. After response, `unbind_contextvars()` cleans up

## Next Steps

1. Review this guide and the README.md
2. Start with Wave 1: `/task-work TASK-LOG-001`
3. Progress through waves sequentially
4. Wave 3 tasks can be run in parallel
