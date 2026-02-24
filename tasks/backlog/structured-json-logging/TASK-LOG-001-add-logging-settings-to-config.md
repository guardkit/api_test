---
id: TASK-LOG-001
title: Add logging settings to core config
task_type: scaffolding
parent_review: TASK-REV-E19E
feature_id: FEAT-LOG
status: blocked
priority: high
complexity: 2
wave: 1
implementation_mode: direct
dependencies: []
estimated_minutes: 20
tags:
- logging
- config
autobuild_state:
  current_turn: 3
  max_turns: 5
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-3CC2
  base_branch: main
  started_at: '2026-02-24T15:35:03.663993'
  last_updated: '2026-02-24T15:52:44.718593'
  turns:
  - turn: 1
    decision: feedback
    feedback: "- Not all acceptance criteria met:\n  \u2022 `Settings` class has `log_level`\
      \ field with default \"INFO\"\n  \u2022 `Settings` class has `log_format` field\
      \ with default \"json\"\n  \u2022 `log_level` is configurable via `LOG_LEVEL`\
      \ environment variable\n  \u2022 `log_format` is configurable via `LOG_FORMAT`\
      \ environment variable\n  \u2022 `.env.example` updated with new variables\n\
      \  (2 more)"
    timestamp: '2026-02-24T15:35:03.663993'
    player_summary: Added log_level and log_format fields to Settings class following
      the existing pydantic-settings pattern. The environment variable resolution
      is automatic (LOG_LEVEL -> log_level). Updated .env.example with the new variables
      and added structlog>=24.1.0 to requirements/base.txt. Created comprehensive
      tests in tests/test_config.py covering default values and environment variable
      configuration.
    player_success: true
    coach_success: true
  - turn: 2
    decision: feedback
    feedback: "- Not all acceptance criteria met:\n  \u2022 `Settings` class has `log_level`\
      \ field with default \"INFO\"\n  \u2022 `Settings` class has `log_format` field\
      \ with default \"json\"\n  \u2022 `log_level` is configurable via `LOG_LEVEL`\
      \ environment variable\n  \u2022 `log_format` is configurable via `LOG_FORMAT`\
      \ environment variable\n  \u2022 `.env.example` updated with new variables\n\
      \  (2 more)"
    timestamp: '2026-02-24T15:41:56.031949'
    player_summary: 'Direct mode SDK invocation completed (git-detected: 1 modified,
      2 created)'
    player_success: true
    coach_success: true
  - turn: 3
    decision: feedback
    feedback: "- Not all acceptance criteria met:\n  \u2022 `Settings` class has `log_level`\
      \ field with default \"INFO\"\n  \u2022 `Settings` class has `log_format` field\
      \ with default \"json\"\n  \u2022 `log_level` is configurable via `LOG_LEVEL`\
      \ environment variable\n  \u2022 `log_format` is configurable via `LOG_FORMAT`\
      \ environment variable\n  \u2022 `.env.example` updated with new variables\n\
      \  (2 more)"
    timestamp: '2026-02-24T15:44:35.322694'
    player_summary: 'Direct mode SDK invocation completed (git-detected: 4 modified,
      4 created)'
    player_success: true
    coach_success: true
---

# Task: Add logging settings to core config

## Description

Add logging-related configuration fields to `src/core/config.py` Settings class and update `.env.example` with corresponding environment variables. This provides the foundation for all subsequent logging tasks.

## Changes Required

### `src/core/config.py`
Add to the `Settings` class:
- `log_level: str = "INFO"` - Configurable log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `log_format: str = "json"` - Log output format ("json" for production, "console" for development)

### `.env.example`
Add:
- `LOG_LEVEL=INFO`
- `LOG_FORMAT=json`

### `requirements/base.txt`
Add:
- `structlog>=24.1.0`

## Acceptance Criteria

- [ ] `Settings` class has `log_level` field with default "INFO"
- [ ] `Settings` class has `log_format` field with default "json"
- [ ] `log_level` is configurable via `LOG_LEVEL` environment variable
- [ ] `log_format` is configurable via `LOG_FORMAT` environment variable
- [ ] `.env.example` updated with new variables
- [ ] `structlog` added to `requirements/base.txt`
- [ ] Existing tests still pass

## Implementation Notes

- Follow existing Settings pattern in `src/core/config.py`
- Use pydantic-settings env var resolution (LOG_LEVEL -> log_level)
- The `log_format` field enables environment-conditional rendering: "json" for production, "console" for colored dev output
