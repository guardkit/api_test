---
complexity: 5
dependencies: []
feature_id: FEAT-F2B0
id: TASK-F2B0-001
implementation_mode: task-work
parent_review: TASK-REV-F2B0
status: design_approved
task_type: feature
title: Implement user retrieval endpoint
wave: 1
---

# Implement user retrieval endpoint

## Acceptance Criteria

- [ ] GET /users/{id} returns 200 OK with user details for valid ID
- [ ] Response body includes id, name, and email (per ASSUM-001)
- [ ] Endpoint handles database connectivity errors gracefully

## Implementation Notes

- Use the repository pattern for user lookups
- Ensure the endpoint is documented in OpenAPI spec
- All modified files pass project-configured lint/format checks with zero errors

## Seam Tests

The following seam test validates the integration contract with the data layer.

```python
"""Seam test: verify user repository contract."""
import pytest

@pytest.mark.seam
@pytest.mark.integration_contract("user_repository")
def test_user_repository_contract():
    """Verify repository returns user object for valid ID.

    Contract: returns User domain model or raises NotFound
    Producer: TASK-F2B0-001
    """
    # Implementation depends on repository interface
    pass
```