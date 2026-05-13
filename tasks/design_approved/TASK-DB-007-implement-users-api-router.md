---
complexity: 6
dependencies:
- TASK-DB-006
estimated_minutes: 75
feature_id: FEAT-DB
id: TASK-DB-007
implementation_mode: task-work
parent_review: TASK-REV-4B7D
status: design_approved
task_type: feature
title: Implement users API router
wave: 4
---

# Task: Implement Users API Router

## Description

Create the users API router with full CRUD endpoints following FastAPI patterns. Register the router in the main application.

## Acceptance Criteria

- [ ] `src/users/router.py` created with endpoints:
  - `POST /users` - Create a new user (201 response)
  - `GET /users` - List users with pagination (skip/limit query params)
  - `GET /users/{user_id}` - Get user by ID (404 if not found)
  - `PUT /users/{user_id}` - Update user (404 if not found)
  - `DELETE /users/{user_id}` - Delete user (204 no content, 404 if not found)
- [ ] Router uses `get_db` dependency for database sessions
- [ ] Proper HTTP status codes (201 for create, 204 for delete, 404 for not found, 409 for duplicate email)
- [ ] Response models specified for OpenAPI documentation
- [ ] `src/main.py` updated to register `users_router` with prefix `/users` and tag `"users"`
- [ ] OpenAPI tags metadata updated with users description
- [ ] `tests/users/test_router.py` created with full API integration tests:
  - Create user, read user, list users, update user, delete user
  - 404 handling for missing users
  - 409 handling for duplicate email
  - Pagination behavior
- [ ] All tests pass
- [ ] mypy strict mode passes

## Technical Notes

- Use `APIRouter(prefix="/users", tags=["users"])` or register with prefix in `main.py`
- Use `Response(status_code=204)` for delete endpoint
- Use `HTTPException(status_code=404)` for not found errors or custom exceptions
- UUID path parameter: `user_id: UUID`

## Implementation Notes

This is the culminating feature task - brings together models, schemas, CRUD, and dependencies into working API endpoints.