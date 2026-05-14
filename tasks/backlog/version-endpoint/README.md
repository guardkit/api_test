# Feature: GET /version endpoint

**Status**: Planned · **Tasks**: 1 · **Estimated wall-clock**: 25–40 min

Expose service version metadata at `GET /version`:

```json
{
  "service": "api_test",
  "version": "0.1.0",
  "git_sha": "abc1234",
  "build_time": "2026-05-14T08:30:00Z"
}
```

When `APP_GIT_SHA` / `APP_BUILD_TIME` env vars are absent, the
corresponding fields return `"unknown"`. The running app does NOT shell
out to `git`.

## Structure

```
tasks/backlog/version-endpoint/
├── README.md                                    (this file)
├── IMPLEMENTATION-GUIDE.md                      (data flow, files, verification)
└── TASK-VER-001-add-version-endpoint.md         (the single task)
```

## Quick Reference

- **Pattern**: mirrors `src/health/` (feature-module under `src/`)
- **Schema location**: inline in `src/version/router.py` (per spec
  constraint — no separate `schemas.py` for this feature)
- **Version source**: `settings.app_version` (kept in sync with
  `pyproject.toml`'s `[project].version`)
- **Service name source**: `settings.app_name` (default bumped from
  `"api"` to `"api_test"` to match the `pyproject.toml` package name)

## Out of Scope

- Auth on the endpoint
- Caching headers
- Multiple version formats (semver vs date)
- Changing existing endpoint response bodies
- CI/Docker scripting to inject `APP_GIT_SHA` and `APP_BUILD_TIME`
  (separate follow-up — the endpoint accepts the env vars, but wiring
  them through the build pipeline is deployment work)

## Next Steps

```bash
# Inspect the plan
cat tasks/backlog/version-endpoint/IMPLEMENTATION-GUIDE.md

# Run with autobuild (once feature YAML is generated)
/feature-build FEAT-XXXX

# Or work the task manually
/task-work TASK-VER-001
```
