---
id: TASK-READY-003
title: Add smoke test
task_type: testing
parent_review: TASK-REV-D450
feature_id: FEAT-D4
wave: 3
implementation_mode: direct
complexity: 3
dependencies:
  - TASK-READY-002
---
# Add smoke test

## Acceptance Criteria
- [ ] Smoke test verifies GET /ready returns 200 OK
- [ ] Smoke test verifies POST /ready returns 405 Method Not Allowed
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes
- Place test in tests/health/test_readiness.py
- Use pytest framework
- Ensure the test is tagged with @smoke for smoke-gate execution