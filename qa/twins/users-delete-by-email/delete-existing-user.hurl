# HURL TWIN of spec 9.1 — features/users-delete-by-email/users-delete-by-email.feature
# Scenario: An existing user is deleted by their email (APPROVED AS PROPOSED by Rich 2026-07-28)
#
# VERBATIM approved Gherkin:
#
# APPROVED AS PROPOSED by Rich 2026-07-28 (interactive sit; all 4 assumptions confirmed, ASSUM-003 = 404 honest absence)
# @users-delete-by-email
# Feature: Delete User By Email
#   As an operator of the api_test service
#   I want to delete a user by their email address
#   So that I can remove an account without first looking up its id
#
#   Background:
#     Given the api_test service is running with its database available
#
#   # Why: Core path — the deletion actually removes the record (the round-trip:
#   # a subsequent lookup by the same email must honestly miss)
#   @key-example @smoke
#   Scenario: An existing user is deleted by their email
#     Given a user exists with email "ada@example.com"
#     When I delete the user by email "ada@example.com"
#     Then the request should succeed with no content
#     And looking up the user by email "ada@example.com" should find nothing
#
# Translation note: the "Given a user exists" seed is created THROUGH the product
# API (real write path); {{run_marker}} is injected by the gate so re-runs never
# collide with prior data.

POST {{base_url}}/users
Content-Type: application/json
{
  "email": "pilot-{{run_marker}}@example.com",
  "full_name": "Pilot {{run_marker}}"
}
HTTP 201
[Asserts]
jsonpath "$.email" == "pilot-{{run_marker}}@example.com"

DELETE {{base_url}}/users/by-email?email=pilot-{{run_marker}}@example.com
HTTP 204

GET {{base_url}}/users/by-email?email=pilot-{{run_marker}}@example.com
HTTP 404
