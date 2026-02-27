---
autobuild_state:
  base_branch: main
  current_turn: 2
  last_updated: '2026-02-26T19:26:30.961118'
  max_turns: 5
  started_at: '2026-02-26T16:46:26.192691'
  turns:
  - coach_success: true
    decision: feedback
    feedback: "- Not all acceptance criteria met:\n  • When database is reachable:
      returns `status: \"ok\"`, `database: \"connected\"`\n  • When database is unreachable:
      returns `status: \"degraded\"`, `database: \"unavailable\"` (still HTTP 20\n
      \ • Exception handling: database probe failure is caught gracefully, does not
      crash endpoint\n  • Existing health check tests updated for new response structure\n
      \ • New tests added:\n  (2 more)"
    player_success: true
    player_summary: Implementation via task-work delegation
    timestamp: '2026-02-26T16:46:26.192691'
    turn: 1
  - coach_success: true
    decision: feedback
    feedback: "- Tests failed due to infrastructure/environment issues (not code defects).
      Remediation options: (1) Add mock fixtures for external services, (2) Use SQLite
      for test database, (3) Mark integration tests with @pytest.mark.integration
      and exclude via -m 'not integration':\n  Error detail:\n             ^^^^^^^^^^\nE
      \  sqlite3.OperationalError: no such table: users\n\nThe above exception was
      the direct cause of the following exception:\ntests/users/test_crud.py:45: in
      test_create_user_success\nResult:\nFAILED tests/users/test_crud.py::TestDeleteUser::test_delete_user_success
      - s...\nFAILED tests/users/test_crud.py::TestDeleteUser::test_delete_user_not_found\nFAILED
      tests/users/test_crud.py::TestCountUsers::test_count_users_empty - sql...\nFAILED
      tests/users/test_crud.py::TestCountUsers::test_count_users_with_data\n==================
      18 failed, 24 passed, 36 warnings in 4.82s =================="
    player_success: true
    player_summary: Implementation via task-work delegation
    timestamp: '2026-02-26T19:14:15.705934'
    turn: 2
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-947C
complexity: 4
consumer_context:
- consumes: DATABASE_URL
  driver: asyncpg
  format_note: URL must include +asyncpg dialect suffix for async engine; health check
    uses get_db dependency to obtain session
  framework: SQLAlchemy async (AsyncSession)
  task: TASK-DB-001
dependencies:
- TASK-DB-001
- TASK-DB-004
estimated_minutes: 40
feature_id: FEAT-DB
id: TASK-DB-008
implementation_mode: task-work
parent_review: TASK-REV-4B7D
status: design_approved
task_type: feature
title: Integrate database health check
wave: 3
---

# Task: Integrate Database Health Check

## Description

Extend the existing `GET /health` endpoint to include database connectivity status. Add a `database` field to `HealthResponse` that reports whether the database connection is healthy.

## Acceptance Criteria

- [ ] `src/health/schemas.py` updated: `HealthResponse` includes `database: str` field (values: `"connected"` or `"unavailable"`)
- [ ] `src/health/router.py` updated: health endpoint accepts `get_db` dependency, executes `SELECT 1` probe
- [ ] When database is reachable: returns `status: "ok"`, `database: "connected"`
- [ ] When database is unreachable: returns `status: "degraded"`, `database: "unavailable"` (still HTTP 200)
- [ ] Exception handling: database probe failure is caught gracefully, does not crash endpoint
- [ ] Existing health check tests updated for new response structure
- [ ] New tests added:
  - Test healthy database scenario
  - Test degraded scenario (database unavailable) using dependency override
- [ ] All tests pass (including existing health tests)
- [ ] mypy strict mode passes

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify DATABASE_URL contract from TASK-DB-001."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("DATABASE_URL")
def test_database_url_format():
    """Verify DATABASE_URL matches the expected format.

    Contract: URL must include +asyncpg dialect suffix for async engine
    Producer: TASK-DB-001
    """
    import os
    value = os.environ.get("DATABASE_URL", "")

    assert value, "DATABASE_URL must not be empty"
    assert "+asyncpg" in value, f"Expected asyncpg dialect in URL, got: {value}"
```

## Technical Notes

- Use `text("SELECT 1")` for the database probe
- Wrap probe in try/except to handle connection failures gracefully
- Return `status: "degraded"` (not 503) when DB is down - keeps endpoint usable for liveness checks
- This is upgradeable to separate liveness/readiness endpoints later if needed

## Implementation Notes

Modifies existing health endpoint - requires careful handling to not break existing tests. Use dependency override in tests to simulate database failure scenarios.