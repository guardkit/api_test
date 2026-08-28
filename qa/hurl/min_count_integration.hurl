# Integration tests for the /users/count-by-domain endpoint with min_count parameter.
# Variables: {{host}} is set by the runner (e.g. APP_BASE_URL).
# These tests exercise the min_count query parameter across all acceptance criteria.

# ============================================================
# AC-002: Omitting min_count returns all domains (200 OK)
# ============================================================

GET {{host}}/users/count-by-domain
HTTP 200
[Asserts]
jsonpath "$" isCollection

# ============================================================
# AC-003: min_count=0 includes all domains (200 OK)
# ============================================================

GET {{host}}/users/count-by-domain?min_count=0
HTTP 200
[Asserts]
jsonpath "$" isCollection

# ============================================================
# AC-004: Negative min_count returns 400 Bad Request
# ============================================================

GET {{host}}/users/count-by-domain?min_count=-1
HTTP 400
[Asserts]
jsonpath "$.detail" contains "min_count must not be negative"

# ============================================================
# AC-005: min_count exceeding 10,000 returns 400 Bad Request
# ============================================================

GET {{host}}/users/count-by-domain?min_count=10001
HTTP 400
[Asserts]
jsonpath "$.detail" contains "min_count must not exceed 10000"

# ============================================================
# AC-006: Non-integer min_count returns 400 Bad Request
# ============================================================

GET {{host}}/users/count-by-domain?min_count=abc
HTTP 400
[Asserts]
jsonpath "$.detail" contains "min_count must be a valid integer"

# ============================================================
# AC-007: Empty min_count returns 400 Bad Request
# ============================================================

GET {{host}}/users/count-by-domain?min_count=
HTTP 400
[Asserts]
jsonpath "$.detail" contains "min_count must not be empty"

# ============================================================
# AC-008: Very large min_count returns no domains (empty list)
# Note: min_count must be <= 10000 (valid range). We use 1000
# which is valid but exceeds any reasonable domain count.
# ============================================================

GET {{host}}/users/count-by-domain?min_count=1000
HTTP 200
[Asserts]
jsonpath "$" isCollection
jsonpath "$" hasLen 0
