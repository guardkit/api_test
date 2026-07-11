---
id: TASK-VER-001
title: Add GET /version endpoint
status: in_review
priority: high
task_type: feature
tags:
- fastapi
- version
- metadata
complexity: 3
feature_id: FEAT-VER
wave: 1
implementation_mode: direct
dependencies: []
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 5
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-9E59
  base_branch: ddd-demo
  started_at: '2026-07-04T11:07:11.817198'
  last_updated: '2026-07-04T11:13:46.956790'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-07-04T11:07:11.817198'
    player_summary: Successfully implemented GET /version endpoint following FastAPI
      best practices. Added app_git_sha and app_build_time fields to Settings class,
      which auto-bind to APP_GIT_SHA and APP_BUILD_TIME environment variables via
      Pydantic's BaseSettings. Updated app_name default from 'api' to 'api_test'.
      Created new version module with inline VersionResponse Pydantic model and async
      endpoint handler. Registered router in main.py with version tag. All code passes
      mypy strict type checking and ruff formatti
    player_success: true
    coach_success: true
---

# Task: Add GET /version endpoint

## Description

Expose service version metadata at `GET /version` returning the service name,
version, git SHA, and build time. The endpoint must mirror the structural shape
of `src/health/` (feature-module layout under `src/`) but keep its Pydantic
response schema inline in the router module (no separate `schemas.py` for this
feature — the spec is small enough that a single file is clearer).

Version is read from existing settings (`settings.app_version`, which is kept
in sync with `pyproject.toml`'s `[project].version`). Git SHA and build time
are read from `APP_GIT_SHA` and `APP_BUILD_TIME` environment variables via
pydantic-settings, defaulting to the string `"unknown"` when not set. The
running app must NOT shell out to `git`.

## Response Shape

```json
{
  "service": "api_test",
  "version": "0.1.0",
  "git_sha": "abc1234",
  "build_time": "2026-05-14T08:30:00Z"
}
```

When `APP_GIT_SHA` / `APP_BUILD_TIME` are not set in the environment, the
corresponding fields return the literal string `"unknown"`.

## Acceptance Criteria

- [ ] `src/core/config.py` adds two new fields to `Settings`:
  - `app_git_sha: str = "unknown"` (auto-bound to `APP_GIT_SHA` env var)
  - `app_build_time: str = "unknown"` (auto-bound to `APP_BUILD_TIME` env var)
- [ ] `src/core/config.py` updates the default for `app_name` from `"api"` to
      `"api_test"` so the `service` field matches the `pyproject.toml` package
      name without requiring an env override. No other Settings defaults change.
- [ ] `src/version/__init__.py` exists (empty module marker, matching
      `src/health/__init__.py`).
- [ ] `src/version/router.py` defines:
  - An inline Pydantic `VersionResponse` model with four `str` fields:
    `service`, `version`, `git_sha`, `build_time`. Each field has a
    `Field(description=...)`. A `model_config` with `json_schema_extra.examples`
    is included (mirrors `HealthResponse`).
  - An `APIRouter` exposing `GET /version` with:
    - `response_model=VersionResponse`
    - `tags=["version"]`
    - `summary` and `description` strings (concise, one line each)
    - A 200 response example in the `responses=` dict
  - Handler body reads `settings.app_name`, `settings.app_version`,
    `settings.app_git_sha`, `settings.app_build_time` and returns a
    `VersionResponse`. The handler does not read environment variables
    directly — all config flows through `settings`.
- [ ] `src/main.py` imports `from src.version.router import router as version_router`
      and calls `app.include_router(version_router)` alongside `health_router`
      and `users_router`. The new tag `{"name": "version", "description": ...}`
      is appended to the `openapi_tags=` list. No other lines in `main.py`
      change.
- [ ] `tests/version/__init__.py` exists.
- [ ] `tests/version/test_router.py` contains a single happy-path test
      (e.g. `test_version_endpoint_returns_200_with_all_fields`) using the
      `async_client` fixture from `tests/conftest.py`. It asserts:
  - `response.status_code == 200`
  - All four keys (`service`, `version`, `git_sha`, `build_time`) are present
    in the JSON body
  - Each value is a non-empty `str`
  - `service == "api_test"` and `version == "0.1.0"` (matches defaults so the
    test is deterministic without env setup)
  - `git_sha == "unknown"` and `build_time == "unknown"` (the env-unset
    fallback; we do not set `APP_GIT_SHA` / `APP_BUILD_TIME` in the test
    environment)
- [ ] `pytest tests/version/ -v` passes locally.
- [ ] `pytest --cov=src --cov-report=term` continues to pass with ≥80% line
      coverage and ≥75% branch coverage (no regression).
- [ ] `mypy src/` passes (strict).
- [ ] `ruff check src/ tests/` passes.
- [ ] All modified files pass project-configured lint/format checks with zero
      errors.

## Implementation Notes

- **Service name source**: `settings.app_name`. The Settings default is being
  bumped from `"api"` to `"api_test"` so it matches `pyproject.toml` without
  needing `APP_NAME=api_test` in `.env`. This is the only change to an
  existing Settings field — the change is metadata-only (it affects the
  OpenAPI document `title` but no endpoint behaviour or response payload of
  existing endpoints).
- **Version source**: `settings.app_version` (existing, defaults to `"0.1.0"`).
  Keeping the existing pattern — `pyproject.toml`'s `[project].version` and
  `Settings.app_version` are kept in sync manually, matching what `/health`
  already does.
- **Env var binding**: `pydantic-settings` auto-maps `APP_GIT_SHA` →
  `app_git_sha` and `APP_BUILD_TIME` → `app_build_time` (the `SettingsConfigDict`
  default is uppercase-field-name with no special prefix; verify by inspecting
  the existing `app_version` field, which is currently overridable via
  `APP_VERSION`). No custom `Field(validation_alias=...)` is required.
- **`build_time` format**: spec says ISO 8601 UTC or `"unknown"`. The runtime
  app does not parse or validate the value — it just echoes whatever is in
  the env var. The build pipeline (CI) is responsible for setting a valid
  ISO 8601 string; bad input gracefully returns the raw string in the
  response. The `VersionResponse` field is typed as plain `str`, not
  `datetime`, deliberately — this preserves the `"unknown"` sentinel.
- **No shelling out to git**: the running app reads `APP_GIT_SHA` only. If
  this env var is missing, return `"unknown"`. The CI/build system is
  responsible for injecting the short SHA at build time (e.g.
  `APP_GIT_SHA=$(git rev-parse --short HEAD)` in the Dockerfile or deploy
  script). This is documented in the README of this feature folder, not in
  the codebase, since deployment scripting is out of scope.
- **Router prefix strategy**: include with empty prefix so the endpoint is
  exactly `/version` (not `/version/version`). Matches how `/health` is
  registered.
- **Why inline `VersionResponse` (not a separate `schemas.py`)**: the spec
  constraint says "Pydantic response schema in the router module". This
  also keeps the diff surface small — five files touched instead of six.
  If a `VersionRequest` or additional schemas appear later, splitting into
  `src/version/schemas.py` is a clean follow-up.
- **Test fixture reuse**: `async_client` is already provided by
  `tests/conftest.py`. The `/version` endpoint has no DB dependency, so the
  test does NOT need the `override_get_db` fixture.
- **Coverage**: a single happy-path test is sufficient for the four-field
  body assertion (per spec). Branch coverage on the handler is trivial — no
  conditionals exist in the handler body; the env-default fallback is
  handled by pydantic-settings, not by handler code.

## Files Touched (exhaustive)

Modified:
- `src/core/config.py` — add 2 new fields, bump 1 default
- `src/main.py` — import + include_router + openapi_tags entry

Created:
- `src/version/__init__.py`
- `src/version/router.py`
- `tests/version/__init__.py`
- `tests/version/test_router.py`

## Coach Validation Commands

```bash
pytest tests/version/ -v
pytest --cov=src --cov-report=term --cov-fail-under=80
mypy src/
ruff check src/ tests/
ruff format --check src/ tests/
```

## Out of Scope

- Auth on the endpoint (anonymous access intentional — version is
  metadata, not sensitive).
- Caching headers (`Cache-Control`, `ETag`) — out of scope.
- Multiple version representations (semver vs date vs CalVer).
- Reading `git_sha` by shelling out to `git` at runtime.
- Any change to `/health`, `/users/*`, or other existing endpoints'
  response bodies. (The metadata-only `app_name` default change does
  not change any existing response payload.)
- Splitting `VersionResponse` into a separate `src/version/schemas.py`.
