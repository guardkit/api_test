---
id: TASK-F811-001
title: Implement version endpoint
task_type: feature
parent_review: TASK-REV-F811
feature_id: FEAT-F811
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
---

# Implement version endpoint

Implement the `/version` endpoint that returns application version and git commit hash.

## Acceptance Criteria

- [ ] GET `/version` returns 200 OK
- [ ] Response body contains `version` (string) and `commit` (40-char hex string)
- [ ] Response content-type is `application/json`
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

The commit hash should be injected via environment variables at startup. The endpoint should be accessible without authentication.

## Seam Tests

No cross-task data dependencies identified.