---
id: TASK-LOG-001
title: Add logging settings to core config
task_type: scaffolding
parent_review: TASK-REV-E19E
feature_id: FEAT-LOG
status: pending
priority: high
complexity: 2
wave: 1
implementation_mode: direct
dependencies: []
estimated_minutes: 20
tags: [logging, config]
---

# Task: Add logging settings to core config

## Description

Add logging-related configuration fields to `src/core/config.py` Settings class and update `.env.example` with corresponding environment variables. This provides the foundation for all subsequent logging tasks.

## Changes Required

### `src/core/config.py`
Add to the `Settings` class:
- `log_level: str = "INFO"` - Configurable log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `log_format: str = "json"` - Log output format ("json" for production, "console" for development)

### `.env.example`
Add:
- `LOG_LEVEL=INFO`
- `LOG_FORMAT=json`

### `requirements/base.txt`
Add:
- `structlog>=24.1.0`

## Acceptance Criteria

- [ ] `Settings` class has `log_level` field with default "INFO"
- [ ] `Settings` class has `log_format` field with default "json"
- [ ] `log_level` is configurable via `LOG_LEVEL` environment variable
- [ ] `log_format` is configurable via `LOG_FORMAT` environment variable
- [ ] `.env.example` updated with new variables
- [ ] `structlog` added to `requirements/base.txt`
- [ ] Existing tests still pass

## Implementation Notes

- Follow existing Settings pattern in `src/core/config.py`
- Use pydantic-settings env var resolution (LOG_LEVEL -> log_level)
- The `log_format` field enables environment-conditional rendering: "json" for production, "console" for colored dev output
