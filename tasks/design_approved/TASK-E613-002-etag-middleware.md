---
complexity: 5
dependencies:
- TASK-E613-001
feature_id: FEAT-E613
id: TASK-E613-002
implementation_mode: task-work
parent_review: TASK-REV-E613-PLAN
status: design_approved
task_type: feature
title: Add ETag validation middleware
wave: 2
---

# Add ETag validation middleware

## Acceptance Criteria

- Middleware intercepts GET requests with `If-None-Match` header
- Middleware compares `If-None-Match` with generated ETag
- Returns 304 Not Modified if match
- Returns 200 OK with full body if no match
- Handles malformed `If-None-Match` gracefully (returns full resource)
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Middleware should be reusable across endpoints
- Ensure it integrates with existing response handling
- Consider caching the ETag for performance if appropriate

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify ETag middleware contract from TASK-E613-001."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("ETag middleware")
def test_etag_middleware_format():
    """Verify ETag middleware matches the expected format.

    Contract: Middleware must return 304 for matching If-None-Match and 200 for non-matching
    Producer: TASK-E613-001
    """
    # Producer side: get the ETag from the resource
    etag = ""  # e.g., response.headers.get("ETag")

    # Consumer side: verify format matches contract
    assert etag, "ETag header must be present"
    assert etag.startswith('"') and etag.endswith('"'), "ETag must be quoted"
```