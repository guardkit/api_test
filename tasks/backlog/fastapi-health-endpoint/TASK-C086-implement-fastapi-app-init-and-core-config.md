---
id: TASK-C086
title: Implement FastAPI app init and core config
status: backlog
created: 2026-02-23T00:00:00Z
updated: 2026-02-23T00:00:00Z
priority: high
task_type: feature
tags: [fastapi, config, app-init]
complexity: 3
parent_review: TASK-21B6
feature_id: FEAT-HEALTH
wave: 2
implementation_mode: task-work
dependencies:
  - TASK-70ED
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Implement FastAPI app init and core config

## Description

Create the FastAPI application instance in `src/main.py` and a settings module in `src/core/config.py` using Pydantic `BaseSettings`. The app should start cleanly with `uvicorn src.main:app`. No endpoints are wired in this task (that comes in TASK-ED5F).

## Acceptance Criteria

- [ ] `src/core/config.py` defines a `Settings` class using `pydantic-settings` (`BaseSettings`) with at minimum:
  - `app_name: str = "api"`
  - `app_env: str = "development"`
  - `debug: bool = False`
- [ ] Settings reads from environment / `.env` file via `model_config = SettingsConfigDict(env_file=".env")`
- [ ] A module-level `settings = Settings()` singleton is exported
- [ ] `src/main.py` creates the `FastAPI` app instance using `settings.app_name`
- [ ] App includes standard metadata: `title`, `version="0.1.0"`, `debug=settings.debug`
- [ ] `uvicorn src.main:app --reload` starts without errors
- [ ] `mypy src/` passes (strict)
- [ ] `ruff check src/` passes

## Implementation Notes

- Import path: `from src.core.config import settings`
- Do NOT add routers in this task — keep `main.py` minimal, routers added in TASK-ED5F
- `pydantic-settings` is a separate package from `pydantic` v2 — add `pydantic-settings>=2.0` to `requirements/base.txt`
- Use `lifespan` context manager pattern (not deprecated `on_event`) for any future startup/shutdown hooks, even if empty now

## Test Execution Log

[Automatically populated by /task-work]
