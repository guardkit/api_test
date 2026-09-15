---
complexity: 5
dependencies:
- TASK-A0AE-003
feature_id: FEAT-A0AE
id: TASK-A0AE-004
implementation_mode: task-work
parent_review: TASK-REV-A0AE
status: design_approved
task_type: feature
title: Implement analytics service layer
wave: 4
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