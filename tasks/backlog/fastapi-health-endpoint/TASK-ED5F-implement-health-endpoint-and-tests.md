---
id: TASK-ED5F
title: Implement health endpoint and tests
status: in_review
created: 2026-02-23 00:00:00+00:00
updated: 2026-02-23 00:00:00+00:00
priority: high
task_type: feature
tags:
- fastapi
- health
- testing
complexity: 3
parent_review: TASK-21B6
feature_id: FEAT-HEALTH
wave: 3
implementation_mode: task-work
dependencies:
- TASK-C086
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 5
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-EC3C
  base_branch: main
  started_at: '2026-02-24T13:31:04.159245'
  last_updated: '2026-02-24T13:41:49.811801'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-02-24T13:31:04.159245'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: Implement health endpoint and tests

## Description

Implement the `GET /health` endpoint as a proper feature module (`src/health/`), wire it into the FastAPI app, and write tests that achieve the project's coverage targets (80% line, 75% branch).

## Acceptance Criteria

- [ ] `src/health/schemas.py` defines a `HealthResponse` Pydantic model:
  ```python
  class HealthResponse(BaseModel):
      status: str          # e.g. "ok"
      version: str         # e.g. "0.1.0"
  ```
- [ ] `src/health/router.py` defines an `APIRouter` with:
  - `GET /health` → returns `HealthResponse(status="ok", version=settings.app_version)`
  - Response model: `HealthResponse`
  - Tags: `["health"]`
- [ ] `src/main.py` includes the health router with prefix `""` (endpoint is at `/health`, not `/health/health`)
- [ ] `tests/health/test_router.py` covers:
  - `GET /health` returns HTTP 200
  - Response body matches `{"status": "ok", "version": "0.1.0"}`
  - Response `Content-Type` is `application/json`
- [ ] `pytest --cov=src --cov-report=term` passes with ≥80% line coverage
- [ ] `mypy src/` passes (strict)
- [ ] `ruff check src/ tests/` passes

## Implementation Notes

- Use `httpx.AsyncClient` with `ASGITransport` (not `TestClient`) for async-compatible tests
- `conftest.py` at `tests/` level should provide an `async_client` fixture
- Add `app_version: str = "0.1.0"` to `Settings` in `src/core/config.py`
- Router prefix strategy: include router with `prefix=""` so endpoint is `/health`
  ```python
  # src/main.py
  from src.health.router import router as health_router
  app.include_router(health_router)
  ```
- No auth, no DB — keep the implementation minimal

## Test Execution Log

[Automatically populated by /task-work]
