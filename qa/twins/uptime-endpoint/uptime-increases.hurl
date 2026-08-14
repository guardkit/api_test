# HURL TWIN of spec 2.2 — features/uptime-endpoint/uptime-endpoint.feature
# Scenario: Uptime increases between consecutive requests (approved-by-curation)
#
# VERBATIM approved Gherkin:
#
# @uptime-endpoint
# Feature: Service Uptime Endpoint
#   As an operator monitoring the api_test service
#   I want to query how long the service has been running
#   So that I can observe service availability and detect restarts
#
#   Background:
#     Given the api_test service is running
#
#   # Why: Uptime must actually measure elapsed time — also the deploy-smoke behaviour check
#   # [ASSUMPTION: confidence=medium] The process start time is captured once at application startup and is stable across requests
#   @key-example @smoke
#   Scenario: Uptime increases between consecutive requests
#     When I request the service uptime twice in succession
#     Then the second reported uptime should be greater than the first
#     And both should report the same process start time

GET {{base_url}}/uptime
HTTP 200
[Captures]
u1: jsonpath "$.uptime_seconds"
s1: jsonpath "$.started_at"

GET {{base_url}}/uptime
HTTP 200
[Asserts]
jsonpath "$.uptime_seconds" > {{u1}}
jsonpath "$.started_at" == "{{s1}}"
