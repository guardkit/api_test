# HURL TWIN of spec 9.4 — features/users-delete-by-email/users-delete-by-email.feature
# Scenario: Deleting the same email twice reports not found the second time
# (APPROVED AS PROPOSED by Rich 2026-07-28; ASSUM-003 = 404 honest absence — the Rich-ruled bar)
#
# VERBATIM approved Gherkin:
#
# APPROVED AS PROPOSED by Rich 2026-07-28 (interactive sit; all 4 assumptions confirmed, ASSUM-003 = 404 honest absence)
# @users-delete-by-email
# Feature: Delete User By Email
#
#   Background:
#     Given the api_test service is running with its database available
#
#   # Why: A second delete of the same email finds nothing — the absence is
#   # reported honestly, never a fabricated success
#   @edge-case
#   Scenario: Deleting the same email twice reports not found the second time
#     Given a user exists with email "once@example.com"
#     When I delete the user by email "once@example.com"
#     And I delete the user by email "once@example.com" again
#     Then the second request should fail with a not-found response
#
# Translation note: the seed is created THROUGH the product API; a distinct
# "pilot-dd-" marker prefix keeps this twin's data disjoint from spec 9.1's twin.

POST {{base_url}}/users
Content-Type: application/json
{
  "email": "pilot-dd-{{run_marker}}@example.com",
  "full_name": "Pilot DD {{run_marker}}"
}
HTTP 201

DELETE {{base_url}}/users/by-email?email=pilot-dd-{{run_marker}}@example.com
HTTP 204

DELETE {{base_url}}/users/by-email?email=pilot-dd-{{run_marker}}@example.com
HTTP 404
