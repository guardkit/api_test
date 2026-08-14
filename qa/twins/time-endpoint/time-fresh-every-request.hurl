# HURL TWIN of spec 6.2 — features/time-endpoint/time-endpoint.feature
# Scenario: The time is fresh on every request (APPROVED AS PROPOSED by Rich 2026-07-31)
#
# VERBATIM approved Gherkin:
#
# APPROVED AS PROPOSED by Rich 2026-07-31 (interactive sit; all 3 assumptions confirmed)
# @time-endpoint
# Feature: Server Time Endpoint
#
#   Background:
#     Given the api_test service is running
#
#   # Why: Boundary — the value is computed per request, never cached or frozen
#   # at process start (an uptime-style constant cannot fake a clock)
#   @boundary
#   Scenario: The time is fresh on every request
#     When I send two GET requests to "/time" at least one second apart
#     Then each response's "time" field should parse as a valid ISO-8601 UTC timestamp
#     And the second timestamp should be strictly later than the first
#
# Translation note: ISO-8601 UTC with trailing Z sorts lexicographically in time
# order, so the "strictly later" step is a plain string > on the captured value.

GET {{base_url}}/time
HTTP 200
[Captures]
t1: jsonpath "$.time"
[Asserts]
jsonpath "$.time" matches /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/

GET {{base_url}}/time
[Options]
delay: 1100ms
HTTP 200
[Asserts]
jsonpath "$.time" matches /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/
jsonpath "$.time" > "{{t1}}"
