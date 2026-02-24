---
id: TASK-70ED
title: Create project scaffold
status: in_review
created: 2026-02-23 00:00:00+00:00
updated: 2026-02-23 00:00:00+00:00
priority: high
task_type: scaffolding
tags:
- fastapi
- scaffold
- setup
complexity: 3
parent_review: TASK-21B6
feature_id: FEAT-HEALTH
wave: 1
implementation_mode: task-work
dependencies: []
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 5
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-EC3C
  base_branch: main
  started_at: '2026-02-24T13:04:59.552866'
  last_updated: '2026-02-24T13:12:01.612714'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-02-24T13:04:59.552866'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: Create project scaffold

## Description

Set up the full project directory structure, dependency configuration, and tooling following the FastAPI production-ready template defined in CLAUDE.md. This is the walking skeleton — all subsequent tasks build on top of it.

No application code is written in this task.

## Acceptance Criteria

- [ ] `pyproject.toml` created with project metadata, ruff, mypy, and pytest configuration
- [ ] `requirements/base.txt` contains production dependencies (fastapi, uvicorn[standard], pydantic>=2.0)
- [ ] `requirements/dev.txt` contains dev dependencies (pytest, pytest-asyncio, httpx, pytest-cov, ruff, mypy)
- [ ] Directory tree created:
  ```
  src/
  ├── health/
  ├── core/
  tests/
  └── health/
  ```
- [ ] `src/__init__.py`, `src/health/__init__.py`, `src/core/__init__.py`, `tests/__init__.py`, `tests/health/__init__.py` all exist (empty)
- [ ] `.env.example` created with placeholder vars (e.g. `APP_ENV=development`)
- [ ] `ruff check .` passes with zero errors on the empty scaffold
- [ ] `mypy src/` passes on empty package files

## Implementation Notes

- Use `pyproject.toml` (not `setup.py`) as the single source of truth for tooling config
- ruff rules: `["E", "F", "I", "UP"]` minimum
- mypy: `strict = true`
- pytest asyncio mode: `asyncio_mode = "auto"`
- Do NOT install a database driver yet (no DB needed for health endpoint)

## Test Execution Log

[Automatically populated by /task-work]
