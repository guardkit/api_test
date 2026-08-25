---
id: TASK-7CEA-002
title: Implement domain extraction logic
task_type: feature
parent_review: TASK-REV-7CEA
feature_id: FEAT-7CEA
wave: 2
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-7CEA-001
status: pending
---

# Implement domain extraction logic

Extract email domains from user data and group counts.

## Acceptance Criteria

- Correctly extracts domain from valid email addresses
- Ignores malformed email addresses
- Handles edge cases (no domain, invalid format)
- All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Use regex or string splitting for domain extraction
- Ensure case-insensitivity for domain matching
- Test with various email formats

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify domain_extraction contract from TASK-7CEA-001."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("domain_extraction")
def test_domain_extraction_format():
    """Verify domain_extraction matches the expected format.

    Contract: returns domain string and count integer
    Producer: TASK-7CEA-001
    """
    # Producer side: get the extracted domains
    domains = extract_domains(["user@example.com", "admin@domain.org"])

    # Consumer side: verify format matches contract
    assert len(domains) == 2
    assert domains[0] == "example.com"
    assert domains[1] == "domain.org"
```