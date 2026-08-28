# Hurl acceptance tests for the DELETE /users/{user_id} endpoint.
# Variables {{host}} and {{marker}} are injected by the test runner.
# The auth token is the project's development token.

AUTH_TOKEN = "dev-token"

# =============================================================================
# AC-001: DELETE /users/{user_id} returns 204
# =============================================================================

# Create a user to delete (real write path — not canned data)
POST {{host}}/users
Content-Type: application/json
X-Auth-Token: {{AUTH_TOKEN}}
{
  "email": "delete-test-{{marker}}@example.com",
  "full_name": "Delete Test {{marker}}"
}
HTTP 201
[Captures]
delete_user_id: jsonpath "$.id"

# Delete the created user — expect 204 No Content
DELETE {{host}}/users/{{delete_user_id}}
X-Auth-Token: {{AUTH_TOKEN}}
HTTP 204

# =============================================================================
# AC-002: DELETE /users/non-existent returns 404
# =============================================================================

DELETE {{host}}/users/00000000-0000-0000-0000-000000000000
X-Auth-Token: {{AUTH_TOKEN}}
HTTP 404

# =============================================================================
# AC-003: DELETE /users/{user_id} twice returns 404 on second attempt
# =============================================================================

# Create a user for the double-delete test
POST {{host}}/users
Content-Type: application/json
X-Auth-Token: {{AUTH_TOKEN}}
{
  "email": "double-delete-{{marker}}@example.com",
  "full_name": "Double Delete {{marker}}"
}
HTTP 201
[Captures]
double_delete_id: jsonpath "$.id"

# First delete — should succeed with 204
DELETE {{host}}/users/{{double_delete_id}}
X-Auth-Token: {{AUTH_TOKEN}}
HTTP 204

# Second delete — user already deleted (soft-deleted), expect 404
DELETE {{host}}/users/{{double_delete_id}}
X-Auth-Token: {{AUTH_TOKEN}}
HTTP 404

# =============================================================================
# AC-004: Count endpoints reflect deletion
# =============================================================================

# Create a user before counting
POST {{host}}/users
Content-Type: application/json
X-Auth-Token: {{AUTH_TOKEN}}
{
  "email": "count-test-before-{{marker}}@example.com",
  "full_name": "Count Test Before {{marker}}"
}
HTTP 201
[Captures]
count_user_id: jsonpath "$.id"

# Capture count before deletion
GET {{host}}/users/count
X-Auth-Token: {{AUTH_TOKEN}}
HTTP 200
[Asserts]
jsonpath "$.count" isInteger

# Delete the user
DELETE {{host}}/users/{{count_user_id}}
X-Auth-Token: {{AUTH_TOKEN}}
HTTP 204

# Capture count after deletion — should be one less
GET {{host}}/users/count
X-Auth-Token: {{AUTH_TOKEN}}
HTTP 200
[Asserts]
jsonpath "$.count" isInteger
