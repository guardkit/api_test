---
id: TASK-LOG-004
title: Integrate logging config with health endpoint
task_type: feature
parent_review: TASK-REV-E19E
feature_id: FEAT-LOG
status: pending
priority: normal
complexity: 3
wave: 3
implementation_mode: direct
dependencies:
  - TASK-LOG-002
estimated_minutes: 30
tags: [logging, health, observability]
consumer_context:
  - task: TASK-LOG-002
    consumes: STRUCTLOG_LOGGER
    framework: "structlog bound logger via get_logger()"
    driver: "structlog"
    format_note: "Logger must be obtained via get_logger() from src.core.logging"
---

# Task: Integrate logging config with health endpoint

## Description

Update the existing health endpoint to expose logging configuration status. This allows operators to verify log settings without checking environment variables or config files.

## Changes Required

### `src/health/schemas.py`
Add optional logging fields to `HealthResponse`:
- `log_level: str` - Current configured log level (e.g., "INFO")
- `log_format: str` - Current configured log format (e.g., "json")

### `src/health/router.py`
Update `health_check()` to include logging config from Settings:
- Read `settings.log_level` and `settings.log_format`
- Return in response alongside existing `status` and `version`

## Acceptance Criteria

- [ ] `HealthResponse` schema includes `log_level` and `log_format` fields
- [ ] `GET /health` returns current log level and format
- [ ] Existing health endpoint fields (`status`, `version`) unchanged
- [ ] OpenAPI schema updated with new fields and examples
- [ ] Existing health endpoint tests updated

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify STRUCTLOG_LOGGER contract from TASK-LOG-002."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("STRUCTLOG_LOGGER")
def test_logging_config_accessible_for_health():
    """Verify logging config settings are accessible for health endpoint.

    Contract: Settings must expose log_level and log_format fields
    Producer: TASK-LOG-001 (via TASK-LOG-002 dependency chain)
    """
    from src.core.config import settings

    assert hasattr(settings, "log_level"), "Settings must have log_level field"
    assert hasattr(settings, "log_format"), "Settings must have log_format field"
    assert isinstance(settings.log_level, str), "log_level must be a string"
    assert isinstance(settings.log_format, str), "log_format must be a string"
```

## Implementation Notes

- Follow existing `HealthResponse` pattern in `src/health/schemas.py`
- The health endpoint already imports `settings` from `src.core.config`
- Update the `json_schema_extra` examples to include the new fields
