# Runtime smoke — /users round-trip, over the wire (Hurl executor).
# Source: the accepted worked examples in features/runtime-smoke/runtime-smoke.feature
# (the same behaviour tests/acceptance/users_roundtrip.py verifies in Python — this is the A/B).
# Self-contained (Hurl has no includes); {{host}} and {{marker}} come from the wrapper.
# The seed "Given" is NOT here: it is created THROUGH the product API below (a real write path).

# --- Given a user carrying the per-run marker is created through the service (real write) ---
POST {{host}}/users
Content-Type: application/json
{
  "email": "seeded-{{marker}}@smoke.internal",
  "full_name": "Seeded {{marker}}"
}
HTTP 201
[Captures]
seeded_id: jsonpath "$.id"

# --- Then the seeded marker is visible through the running service (anti-stub: canned data can't know the marker) ---
GET {{host}}/users
HTTP 200
[Asserts]
jsonpath "$.items" isCollection
jsonpath "$.items[*].email" contains "seeded-{{marker}}@smoke.internal"

# --- When a new user is created and fetched back, the details match (real read-back) ---
POST {{host}}/users
Content-Type: application/json
{
  "email": "readback-{{marker}}@smoke.internal",
  "full_name": "Readback {{marker}}"
}
HTTP 201
[Captures]
rb_id: jsonpath "$.id"
[Asserts]
jsonpath "$.email" == "readback-{{marker}}@smoke.internal"

GET {{host}}/users/{{rb_id}}
HTTP 200
[Asserts]
jsonpath "$.id" == "{{rb_id}}"
jsonpath "$.email" == "readback-{{marker}}@smoke.internal"
jsonpath "$.full_name" == "Readback {{marker}}"

# --- Negative: a never-created id is 404 ---
GET {{host}}/users/00000000-0000-0000-0000-000000000000
HTTP 404

# --- Negative: a duplicate email is 409 ---
POST {{host}}/users
Content-Type: application/json
{
  "email": "seeded-{{marker}}@smoke.internal",
  "full_name": "Dup {{marker}}"
}
HTTP 409

# --- Negative: a malformed payload is 422 ---
POST {{host}}/users
Content-Type: application/json
{
  "full_name": "No Email {{marker}}"
}
HTTP 422
