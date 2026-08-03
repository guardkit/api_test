---
id: TASK-GRO1-001
title: Add GET /whoami endpoint with tests
task_type: implementation
feature_id: FEAT-GRO1
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
---

## Acceptance Criteria

- [ ] GET /whoami returns 200 with JSON body `{"service": "api_test"}`
- [ ] POST /whoami returns 405 (method not allowed)
- [ ] Implemented as a new `src/whoami/` module (router + response schema) wired into `src/main.py`, mirroring the `src/version/` pattern
- [ ] Test suite in `tests/whoami/` covers the happy path, method rejection, and exact JSON structure
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- Mirror the `src/version/` and `src/time/` module shape exactly (router file, response model, registration in `src/main.py`).
- Keep the payload static and deterministic — no environment reads, no I/O, no clock.
- Use the existing pytest patterns from `tests/version/` (or `tests/health/`); tests must be hermetic.
