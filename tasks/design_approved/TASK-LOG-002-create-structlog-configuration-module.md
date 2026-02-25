---
complexity: 5
consumer_context:
- consumes: LOGGING_SETTINGS
  driver: structlog
  format_note: log_level must be a valid Python logging level string (DEBUG/INFO/WARNING/ERROR/CRITICAL);
    log_format must be 'json' or 'console'
  framework: structlog processor pipeline
  task: TASK-LOG-001
dependencies:
- TASK-LOG-001
estimated_minutes: 60
feature_id: FEAT-LOG
id: TASK-LOG-002
implementation_mode: task-work
parent_review: TASK-REV-E19E
priority: high
status: design_approved
tags:
- logging
- structlog
- config
task_type: feature
title: Create structlog configuration module
wave: 2
---

# Task: Create structlog configuration module

## Description

Create `src/core/logging.py` that configures structlog with a processor pipeline, stdlib logging integration, and environment-conditional rendering. This module is the central logging infrastructure that all other components will use.

## Changes Required

### `src/core/logging.py` (new file)
- `setup_logging()` function that configures structlog and stdlib logging
- Processor pipeline: timestamper, log level, caller info, correlation ID binding, JSON/console renderer
- Environment-conditional rendering: JSON when `log_format == "json"`, colored console when `log_format == "console"`
- `get_logger(name: str)` convenience function that returns a bound structlog logger
- Integration with stdlib logging so uvicorn and SQLAlchemy logs also pass through structlog

### `src/main.py`
- Call `setup_logging()` in the `lifespan()` context manager on startup

## Acceptance Criteria

- [ ] `src/core/logging.py` exists with `setup_logging()` and `get_logger()` functions
- [ ] structlog configured with processor pipeline (timestamp, level, caller info, JSON/console renderer)
- [ ] `setup_logging()` reads `log_level` and `log_format` from Settings
- [ ] JSON output when `log_format == "json"` (production)
- [ ] Colored console output when `log_format == "console"` (development)
- [ ] stdlib logging wrapped so third-party library logs go through structlog
- [ ] `setup_logging()` called in `lifespan()` startup
- [ ] Logger instances correctly bound with structlog context

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify LOGGING_SETTINGS contract from TASK-LOG-001."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("LOGGING_SETTINGS")
def test_logging_settings_format():
    """Verify LOGGING_SETTINGS matches the expected format.

    Contract: log_level must be a valid Python logging level string;
              log_format must be 'json' or 'console'
    Producer: TASK-LOG-001
    """
    from src.core.config import settings

    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    assert settings.log_level.upper() in valid_levels, (
        f"Expected valid log level, got: {settings.log_level}"
    )
    assert settings.log_format in ("json", "console"), (
        f"Expected 'json' or 'console', got: {settings.log_format}"
    )
```

## Implementation Notes

- Use `structlog.configure()` with shared processors
- Use `structlog.stdlib.ProcessorFormatter` to bridge stdlib -> structlog
- The processor chain should include: `structlog.contextvars.merge_contextvars_context` for correlation ID support
- Call `logging.basicConfig()` with structlog's `ProcessorFormatter` to capture stdlib logs