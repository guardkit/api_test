---
autobuild_state:
  base_branch: main
  current_turn: 1
  last_updated: '2026-02-23T17:12:17.343399'
  max_turns: 5
  started_at: '2026-02-23T17:02:38.790902'
  turns:
  - coach_success: true
    decision: approve
    feedback: null
    player_success: true
    player_summary: Implementation via task-work delegation
    timestamp: '2026-02-23T17:02:38.790902'
    turn: 1
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-EC3C
complexity: 3
created: 2026-02-23 00:00:00+00:00
dependencies: []
feature_id: FEAT-HEALTH
id: TASK-70ED
implementation_mode: task-work
parent_review: TASK-21B6
priority: high
status: design_approved
tags:
- fastapi
- scaffold
- setup
task_type: scaffolding
test_results:
  coverage: null
  last_run: null
  status: pending
title: Create project scaffold
updated: 2026-02-23 00:00:00+00:00
wave: 1
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