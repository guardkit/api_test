---
id: TASK-B70F-001
title: Create version endpoint and metadata extraction
task_type: feature
parent_review: TASK-REV-B70F
feature_id: FEAT-B70F
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
---

## Acceptance Criteria

- [ ] GET /version returns JSON with keys: version, commit, service
- [ ] Response contains application version string
- [ ] Response contains 7-character git commit hash
- [ ] Response contains service name
- [ ] All non-GET methods return 405 Method Not Allowed
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Extract build-time metadata from environment variables
- Ensure response format matches /uptime and /stats (flat JSON)
- Use lowercase keys without prefixes

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify version endpoint contract from TASK-B70F-001."""
import pytest

@pytest.mark.seam
@pytest.mark.integration_contract("version_endpoint")
def test_version_endpoint_format():
    """Verify version endpoint matches the expected format.

    Contract: response contains exactly the keys: version, commit, and service
    Producer: TASK-B70F-001
    """
    # Producer side: get the response
    response = requests.get("/version")
    
    # Consumer side: verify format matches contract
    assert response.status_code == 200
    data = response.json()
    for key in ["version", "commit", "service"]:
        assert key in data, f"Expected key {key} in response"
```