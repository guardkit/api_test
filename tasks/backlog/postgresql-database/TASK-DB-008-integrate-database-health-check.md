---
id: TASK-DB-008
title: "Integrate database health check"
task_type: feature
parent_review: TASK-REV-4B7D
feature_id: FEAT-DB
wave: 3
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-DB-001
  - TASK-DB-004
status: pending
estimated_minutes: 40
consumer_context:
  - task: TASK-DB-001
    consumes: DATABASE_URL
    framework: "SQLAlchemy async (AsyncSession)"
    driver: "asyncpg"
    format_note: "URL must include +asyncpg dialect suffix for async engine; health check uses get_db dependency to obtain session"
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
