# Feature Spec Summary: Version Endpoint

**Stack**: generic
**Generated**: 2026-07-09T14:32:00Z
**Scenarios**: 2 total (1 smoke, 0 regression)
**Assumptions**: 1 total (0 high / 0 medium / 1 low confidence)
**Review required**: Yes

## Scope

This specification defines the behavioural contract for a `GET /version` endpoint within the System Metadata bounded context. The endpoint returns a JSON object containing the application version string and the git commit hash used for the build. It is intended to support both human operators and automated monitoring tools in verifying the identity of the deployed binary.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 1 |
| Boundary conditions (@boundary) | 1 |
| Negative cases (@negative) | 1 |
| Edge cases (@edge-case) | 0 |

## Deferred Items

None.

## Open Assumptions (low confidence)

- **ASSUM-001**: The git commit hash returned is the full SHA (40-character hexadecimal string). Basis: Input open question asked 'full SHA, short SHA, or tag?'; no answer provided — defaulting to full SHA as the canonical identifier, but short SHA or tag are equally plausible alternatives.

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "Version Endpoint" --context features/version-endpoint/version-endpoint_summary.md

## Verifier routing (proposed)

- "The version endpoint returns the running build" → hurl
- "The version endpoint rejects an unsupported media type" → hurl