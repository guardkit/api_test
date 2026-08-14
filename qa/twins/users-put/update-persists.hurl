# HURL TWIN of the approved PUT /users/{user_id} contract — src/users/router.py
# (response_model UserPublic, 200 on success, 404 unknown id). NO Gherkin
# .feature file exists for this endpoint (unlike the other twins' verbatim
# headers) — this twin was ORDERED by Rich's 2026-08-14 adjudication of the
# delete twins' catch: crud.update_user shared delete_user's missing-commit
# defect (flush without commit -> the 200 response lies, the row never
# changes), so the update path gets the same one-line fix AND its own
# persistence twin. Semantics twinned, stated in Gherkin form for
# readability (twin's own statement of the ruled semantics, NOT a quoted
# approved spec):
#
# @users-put
# Scenario: An update to a user persists beyond its own request
#   Given a user exists
#   When I update the user's full name via PUT
#   Then the response should show the new full name
#   And fetching the user again should return the SAME new full name
#   And the user's email should be unchanged
#
# Translation note: the seed is created THROUGH the product API (real write
# path); {{run_marker}} is injected by the gate so re-runs never collide. The
# load-bearing assert is the GET-back compare — a flush-without-commit
# regression answers the PUT with 200 + new name, then hands the OLD name
# back on the follow-up GET (exactly the defect class the delete twins
# caught on first contact).

POST {{base_url}}/users
Content-Type: application/json
{
  "email": "pilot-put-{{run_marker}}@example.com",
  "full_name": "Before {{run_marker}}"
}
HTTP 201
[Captures]
user_id: jsonpath "$.id"
[Asserts]
jsonpath "$.email" == "pilot-put-{{run_marker}}@example.com"
jsonpath "$.full_name" == "Before {{run_marker}}"

PUT {{base_url}}/users/{{user_id}}
Content-Type: application/json
{
  "full_name": "After {{run_marker}}"
}
HTTP 200
[Asserts]
jsonpath "$.id" == "{{user_id}}"
jsonpath "$.full_name" == "After {{run_marker}}"
jsonpath "$.email" == "pilot-put-{{run_marker}}@example.com"

GET {{base_url}}/users/{{user_id}}
HTTP 200
[Asserts]
jsonpath "$.full_name" == "After {{run_marker}}"
jsonpath "$.email" == "pilot-put-{{run_marker}}@example.com"
