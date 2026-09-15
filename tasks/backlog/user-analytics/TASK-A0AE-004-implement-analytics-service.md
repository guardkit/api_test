---
id: TASK-A0AE-004
title: Implement analytics service layer
task_type: feature
parent_review: TASK-REV-A0AE
feature_id: FEAT-A0AE
wave: 4
implementation_mode: task-work
complexity: 5
dependencies:
  - TASK-A0AE-003
---

# Implement analytics service layer

Add service layer logic to coordinate analytics retrieval.

## Acceptance Criteria

- [ ] Service method returns daily counts for last 7 days
- [ ] Service handles empty data correctly
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Add to `src/users/calculations.py` or new service file
- Ensure service is injectable
- All modified files must pass project-configured lint/format checks with zero errors