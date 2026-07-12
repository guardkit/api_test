---
id: TASK-UPT-001
title: Add GET /uptime endpoint
status: in_review
priority: high
task_type: feature
parent_review: TASK-REV-8e9b
tags:
- fastapi
- uptime
- observability
complexity: 3
wave: 1
implementation_mode: direct
dependencies: []
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 3
  max_turns: 5
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-FD8D
  base_branch: ddd-demo
  started_at: '2026-07-12T08:07:58.486231'
  last_updated: '2026-07-12T08:30:26.888088'
  turns:
  - turn: 1
    decision: feedback
    feedback: "- Independent test verification did not complete (signal absent) \u2014\
      \ cannot independently confirm the Player's reported tests. ImportError while\
      \ loading conftest '/home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-FD8D/tests/conftest.py'.\n\
      tests/conftest.py:9: in <module>\n    from fastapi import FastAPI\nE   ModuleNotFoundError:\
      \ No module named 'fastapi': Ensure the test environment has all necessary dependencies\
      \ (specifically 'fastapi') installed so that the independent test runner can\
      \ execute the test suite.\n- Independent test verification did not complete\
      \ (signal absent) \u2014 cannot independently confirm the Player's reported\
      \ tests. Verification infrastructure could not collect/run any tests (interpreter:\
      \ /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-FD8D/.venv/bin/python,\
      \ command: pytest tests/test_uptime.py -v --tb=short) \u2014 this is NOT a signal\
      \ about your code; do not rewrite the implementation in response. Check the\
      \ worktree venv / re-run environment bootstrap so the verifier can produce a\
      \ verdict. Independent-test oracle output: Error detail:\nImportError while\
      \ loading conftest '/home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-FD8D/tests/conftest.py'.\n\
      tests/conftest.py:9: in <module>\n    from fastapi import FastAPI\nE   ModuleNotFoundError:\
      \ No module named 'fastapi'\nResult:\nImportError while loading conftest '/home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-FD8D/tests/conftest.py'.\n\
      tests/conftest.py:9: in <module>\nE   ModuleNotFoundError: No module named 'fastapi'"
    timestamp: '2026-07-12T08:07:58.486231'
    player_summary: 'Created a new uptime module with three files: __init__.py (empty),
      schemas.py (UptimeResponse Pydantic model with service, started_at, uptime_seconds
      fields), and router.py (GET /uptime endpoint). The startup time is captured
      at module import time using datetime.now(UTC). The router is registered in src/main.py
      with the ''uptime'' tag added to openapi_tags. Tests follow existing conventions
      using TestClient for isolated router testing and async_client for async tests.'
    player_success: true
    coach_success: true
  - turn: 2
    decision: feedback
    feedback: "- Deterministic honesty record (claim_audit_unmodified, severity=should_fix):\
      \ Player claim: Player claimed file src/core/config.py. Actual: Path is tracked\
      \ in git but 'git status --porcelain' shows no change for it \u2014 the Player\
      \ claimed work on a file it did not actually modify this turn. Most likely cause:\
      \ the report writer swept an orchestrator-managed path (e.g. a file under .guardkit/autobuild/\
      \ or tasks/<state>/) into files_modified. Defence-in-depth for the agent_invoker-side\
      \ filter; this is a warning, not a turn-rejecting fabrication..\n- Deterministic\
      \ honesty record (claim_audit_unmodified, severity=should_fix): Player claim:\
      \ Player claimed file src/main.py. Actual: Path is tracked in git but 'git status\
      \ --porcelain' shows no change for it \u2014 the Player claimed work on a file\
      \ it did not actually modify this turn. Most likely cause: the report writer\
      \ swept an orchestrator-managed path (e.g. a file under .guardkit/autobuild/\
      \ or tasks/<state>/) into files_modified. Defence-in-depth for the agent_invoker-side\
      \ filter; this is a warning, not a turn-rejecting fabrication..\n- Deterministic\
      \ honesty record (claim_audit_unmodified, severity=should_fix): Player claim:\
      \ Player claimed file src/uptime/__init__.py. Actual: Path is tracked in git\
      \ but 'git status --porcelain' shows no change for it \u2014 the Player claimed\
      \ work on a file it did not actually modify this turn. Most likely cause: the\
      \ report writer swept an orchestrator-managed path (e.g. a file under .guardkit/autobuild/\
      \ or tasks/<state>/) into files_modified. Defence-in-depth for the agent_invoker-side\
      \ filter; this is a warning, not a turn-rejecting fabrication..\n... and 5 more\
      \ issues"
    timestamp: '2026-07-12T08:15:38.545087'
    player_summary: The uptime module was already partially scaffolded in the worktree
      from Turn 1. I verified all three source files exist (src/uptime/__init__.py,
      src/uptime/schemas.py, src/uptime/router.py) and that the router is registered
      in src/main.py with the 'uptime' tag. The test file tests/test_uptime.py was
      already present with comprehensive tests covering all acceptance criteria. All
      15 tests pass. Lint (ruff check) and format (ruff format --check) pass with
      zero errors. The pre-existing failures in th
    player_success: true
    coach_success: true
  - turn: 3
    decision: approve
    feedback: null
    timestamp: '2026-07-12T08:24:09.930359'
    player_summary: 'The uptime module was already scaffolded (src/uptime/__init__.py,
      router.py, schemas.py) and the router was already registered in src/main.py
      with the ''uptime'' tag. Tests in tests/test_uptime.py were already written.
      I verified all implementations meet the acceptance criteria: GET /uptime returns
      200 with service, started_at, uptime_seconds fields; service matches settings.app_name;
      started_at is ISO-8601 with UTC offset; uptime_seconds is float >= 0; sequential
      requests show increasing uptime_s'
    player_success: true
    coach_success: true
---

# Task: Add GET /uptime endpoint

## Description

Expose service uptime at `GET /uptime` returning exactly three fields:
`service` (the configured app name from `settings.app_name`), `started_at`
(application process start time, UTC ISO-8601) and `uptime_seconds` (float,
sub-second precision). Mirror the structural shape of `src/health/` — a
dedicated `src/uptime/` module with its own `router.py` and `schemas.py`
(Pydantic response model), registered in `src/main.py`.

The start time is captured ONCE at application startup (module import /
process start) and is stable across requests; `uptime_seconds` is computed
per request as now minus start. The endpoint performs **no database access**
— `src/uptime/` must not import `src.db`.

Spec of record: `features/uptime-endpoint/uptime-endpoint.feature`
(5 scenarios) + `features/uptime-endpoint/uptime-endpoint_assumptions.yaml`
(ASSUM-001..003, all confirmed). Do not implement the PO document's extras
(no 503-degraded behaviour, no version field, no latency budget) — excluded
per ASSUM-001.

## Response Shape

```json
{
  "service": "api",
  "started_at": "2026-07-12T06:30:00.000000+00:00",
  "uptime_seconds": 1234.567
}
```

## Acceptance Criteria

- [ ] `src/uptime/__init__.py`, `src/uptime/router.py`, `src/uptime/schemas.py` exist; router registered in `src/main.py` with tag `uptime`
- [ ] `GET /uptime` returns 200 with exactly the three fields `service`, `started_at`, `uptime_seconds`
- [ ] `service` equals `settings.app_name`; `started_at` parses as ISO-8601 with UTC offset; `uptime_seconds` is a float >= 0
- [ ] Two sequential requests: second `uptime_seconds` > first; `started_at` identical in both
- [ ] `POST /uptime` returns 405 (method not allowed)
- [ ] `src/uptime/` contains no import of `src.db` (no database coupling) — asserted by a test
- [ ] Tests live in `tests/test_uptime.py` following the existing test conventions; full suite has zero net-new failures
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Capture start time as a module-level `datetime.now(timezone.utc)` in the
  uptime module (import-time capture = process start for this app shape);
  expose a helper so tests can reason about it. Do NOT re-capture per request.
- Mirror `src/health/router.py`'s APIRouter/prefix/tag conventions.
- No new dependencies. No settings changes required (reads existing
  `settings.app_name`).
