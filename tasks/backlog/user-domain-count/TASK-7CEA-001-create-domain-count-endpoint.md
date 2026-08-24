---
id: TASK-7CEA-001
title: Create domain count endpoint
task_type: feature
parent_review: TASK-REV-7CEA
feature_id: FEAT-7CEA
wave: 1
implementation_mode: task-work
complexity: 5
dependencies: []
status: pending
---

# Create domain count endpoint

Implement the GET /users/count-by-domain endpoint.

## Acceptance Criteria

- Endpoint returns 200 OK for valid requests
- Returns JSON array of {domain: string, count: number}
- Entries ordered by count descending
- Handles empty user set gracefully

## Implementation Notes

- Use existing user service data access layer
- Ensure endpoint is documented in OpenAPI spec

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify domain_count_endpoint contract from TASK-7CEA-001."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("domain_count_endpoint")
def test_domain_count_endpoint_format():
    """Verify domain_count_endpoint matches the expected format.

    Contract: returns JSON array of objects with domain and count fields
    Producer: TASK-7CEA-001
    """
    # Producer side: get the endpoint response
    response = get_domain_count_response()

    # Consumer side: verify format matches contract
    assert isinstance(response, list)
    for entry in response:
        assert "domain" in entry
        assert "count" in entry
        assert isinstance(entry["domain"], str)
        assert isinstance(entry["count"], int)
```