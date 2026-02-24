---
id: TASK-ADOC-003
title: Add API versioning headers middleware
task_type: feature
parent_review: TASK-REV-7158
feature_id: FEAT-7158
wave: 3
implementation_mode: task-work
complexity: 3
dependencies:
- TASK-ADOC-001
- TASK-ADOC-002
status: in_review
priority: high
tags:
- documentation
- versioning
- middleware
- headers
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 2
  max_turns: 5
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-B2D7
  base_branch: main
  started_at: '2026-02-24T14:29:12.118770'
  last_updated: '2026-02-24T14:40:21.472186'
  turns:
  - turn: 1
    decision: feedback
    feedback: "- Not all acceptance criteria met:\n  \u2022 `src/core/middleware.py`\
      \ exists with `APIVersionHeaderMiddleware`\n  \u2022 Middleware is registered\
      \ in `src/main.py`\n  \u2022 Every API response includes `X-API-Version` header\
      \ with correct version value\n  \u2022 `GET /health` response includes `X-API-Version:\
      \ 0.1.0` header\n  \u2022 `GET /openapi.json` response includes `X-API-Version`\
      \ header\n  (3 more)"
    timestamp: '2026-02-24T14:29:12.118770'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
  - turn: 2
    decision: approve
    feedback: null
    timestamp: '2026-02-24T14:35:52.185096'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: Add API versioning headers middleware

## Description

Add a lightweight ASGI middleware that injects `X-API-Version` response headers on every API response. This provides machine-readable version information for API consumers without introducing route-based versioning complexity.

## Current State

No middleware exists in the project. No API version header is included in responses. The version string is available in `settings.app_version`.

## Implementation Details

### 1. Create middleware module

Create `src/core/middleware.py` with an `APIVersionHeaderMiddleware` class:

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.core.config import settings


class APIVersionHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-API-Version"] = settings.app_version
        return response
```

### 2. Register middleware in main.py

Add the middleware to the FastAPI app in `src/main.py`:

```python
from src.core.middleware import APIVersionHeaderMiddleware

app.add_middleware(APIVersionHeaderMiddleware)
```

### 3. Document the header in OpenAPI schema

Add a global header description. This can be done by documenting it in the API description markdown in the `FastAPI()` constructor's `description` field (already set up in TASK-ADOC-001). Add a note like:

> All responses include an `X-API-Version` header indicating the current API version.

## Acceptance Criteria

- [ ] `src/core/middleware.py` exists with `APIVersionHeaderMiddleware`
- [ ] Middleware is registered in `src/main.py`
- [ ] Every API response includes `X-API-Version` header with correct version value
- [ ] `GET /health` response includes `X-API-Version: 0.1.0` header
- [ ] `GET /openapi.json` response includes `X-API-Version` header
- [ ] API description references the versioning header
- [ ] All existing tests continue to pass
- [ ] New tests verify the header is present on responses

## Test Requirements

- [ ] Test that `GET /health` response has `X-API-Version` header
- [ ] Test that `X-API-Version` header value matches `settings.app_version`
- [ ] Test that header is present on non-endpoint responses (e.g., `/openapi.json`)
- [ ] Test middleware class can be instantiated

## Implementation Notes

Use `BaseHTTPMiddleware` from Starlette (included with FastAPI, no new dependency). This is the simplest middleware pattern for adding response headers. For production high-throughput scenarios, a pure ASGI middleware could be used instead, but `BaseHTTPMiddleware` is appropriate for this project's current state.
