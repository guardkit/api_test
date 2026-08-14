# HURL TWIN of spec 6.1 — features/time-endpoint/time-endpoint.feature
# Scenario: Reading the current server time (APPROVED AS PROPOSED by Rich 2026-07-31)
#
# VERBATIM approved Gherkin:
#
# APPROVED AS PROPOSED by Rich 2026-07-31 (interactive sit; all 3 assumptions confirmed)
# @time-endpoint
# Feature: Server Time Endpoint
#   As a consumer of the api_test service
#   I want to read the server's current time
#   So that I can timestamp client-side operations against the server's clock
#
#   Background:
#     Given the api_test service is running
#
#   # Why: Core path — two exact fields, server-truth time in a machine-parseable
#   # shape (ISO-8601 UTC, second precision, trailing Z)
#   @key-example @smoke
#   Scenario: Reading the current server time
#     When I send a GET request to "/time"
#     Then the response status code should be 200
#     And the response content type should be "application/json"
#     And the response body should contain exactly two fields: "time" and "service"
#     And the "time" field should be the current UTC time in ISO-8601 format with second precision and a trailing "Z"
#     And the "service" field should be "api_test"

GET {{base_url}}/time
HTTP 200
[Asserts]
header "Content-Type" contains "application/json"
jsonpath "$.service" == "api_test"
jsonpath "$.time" matches /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/
jsonpath "$.*" count == 2
