# Deploy Record — TASK-STAT-001 / FEAT-AE43 (GET /stats) — 2026-07-12

**env:** local-compose (`apitest-f2` project, app on host :8901, own postgres internal-only)
**date:** 2026-07-12
**deployer:** Factory-2 coordinator session (headless outer-loop pass, Mode P cid `2dfb4ef5-b769-4a89-91b6-f25498af0090`)
**runbook_ref:** `docker-compose.yml` (cold start: `docker compose -p apitest-f2 up -d --build`)
**deploy_profile_ref:** `deploy/profile.yaml`
**deployed_sha:** `42ba0dd` (the FEAT-AE43 selective-merge receipt, pushed 0/0)

## Claims

- **runtime_claim:** cold compose build+start reaches `healthy`; `GET /health` 200 with
  `database:connected` and both standard headers on the freshly built image carrying /stats.
  **evidence_artifact:** `qa/gates/evidence/FEAT-AE43-local-20260712T145403Z/health-probe-body.json`
  + the `health` gate section of `qa/gates/history/FEAT-AE43-local-20260712T145403Z.json`.
  **committed_at:** 2026-07-12 (same day).

- **runtime_claim:** `GET /stats` is live and behaves per the pinned pass-bar
  (`qa/pass-bar-TASK-STAT-001.yaml`): exact three fields; `requests_served` strictly increased
  across two calls (observed 7→8); `first_request_at` non-null, byte-stable, UTC ISO-8601;
  `POST /stats` → 405.
  **evidence_artifact:** `qa/gates/history/FEAT-AE43-local-20260712T145403Z.json`
  (results envelope, verdict `pass`, exit 0) + `qa/gates/evidence/stats_latest.json`.
  **committed_at:** 2026-07-12 (same day).

## Addenda

- 2026-07-12: live-gate executed via `qa/gates/local_live_gate.py` (the repo's F16-provider
  driver around the unmodified guardkit `LiveGateRunner`) — the plain `guardkit qa live-gate`
  CLI wires no F16 checklist provider and short-circuits `environment_fail`
  (`cli/qa.py:168` / `preflight.py:315`); filed as a guardkit follow-up in the Factory-2 record.
- 2026-07-12: resting state — the `apitest-f2` compose stack is left UP as the deployment of
  record for operator inspection (`docker compose -p apitest-f2 down -v` to tear down). The
  suite's standing Postgres `api-test-pg-factory1` (:5433) is separate and untouched.
