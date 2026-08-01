---
id: TASK-WDG1-001
title: Add the wedge-rehearsal marker module with a test
task_type: feature
feature_id: FEAT-WDG1
wave: 1
implementation_mode: task-work
complexity: 2
dependencies: []
autobuild:
  task_timeout: 120
---

# TASK-WDG1-001: Add the wedge-rehearsal marker module with a test

## Objective

Create `src/wedge_note.py` containing exactly one constant, and one test asserting it.

## Acceptance Criteria

- **AC-001**: `src/wedge_note.py` defines `WEDGE_REHEARSAL = "2026-08-01"` and nothing else of substance.
- **AC-002**: `tests/test_wedge_note.py` asserts the constant equals `"2026-08-01"`.
- **AC-003**: The full test suite still passes.

## Implementation Notes

Deliberately trivial — this is a rehearsal vehicle. No routes, no DB, no config.

## Test Commands (Coach Validation)

```bash
pytest tests/test_wedge_note.py -v --tb=short
```
