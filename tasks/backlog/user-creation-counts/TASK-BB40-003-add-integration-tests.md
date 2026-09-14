---
id: TASK-BB40-003
title: Add integration tests
task_type: testing
parent_review: TASK-REV-BB40
feature_id: FEAT-BB40
wave: 3
implementation_mode: direct
complexity: 3
dependencies:
  - TASK-BB40-002
status: pending
---

## Description

Add integration tests for the daily counts endpoint.

## Acceptance Criteria

- Test returns exactly seven days of data
- Test verifies correct ordering
- Test verifies zero counts for empty days
- Test verifies method rejection

## Implementation Notes

- Use pytest with the existing test suite
- Ensure tests are hermetic and use test database