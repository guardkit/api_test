# Feature: Service Uptime Endpoint

`GET /uptime` returning `service`, `started_at` (UTC ISO-8601) and
`uptime_seconds` (float) — mirrors the `src/health/` module structure, no
database access. Requested via the Mode P planning channel (Factory-1 first
pass, 2026-07-12); spec grounded to the request verbatim.

- **Spec**: `features/uptime-endpoint/uptime-endpoint.feature`
- **Plan**: `IMPLEMENTATION-GUIDE.md` (this folder)
- **Tasks**: `TASK-UPT-001-add-uptime-endpoint.md` (complexity 3, wave 1)
- **Provenance**: `feature_spec_inputs/41a2e3ef-a941-4d8a-9e39-7124f71bf43c.md` → `TASK-REV-8e9b`
