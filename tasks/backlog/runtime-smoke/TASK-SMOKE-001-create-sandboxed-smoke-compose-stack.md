---
id: TASK-SMOKE-001
title: Create sandboxed smoke compose stack
task_type: scaffolding
parent_review: TASK-REV-RSMK
feature_id: FEAT-8737
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
---
# Create sandboxed smoke compose stack

One new file: `deploy/docker-compose.smoke.yml`. A STANDALONE throwaway stack (never layered
on the base compose file) for compose project `apitest-smoke`. It embodies the 2026-07-25
sandbox rulings: pre-built image only, internal-only zero-egress networks, hardened non-root
app container. See docs/runtime-smoke-scope-and-buildplan.md §2.1 and §3 (binding).

## Acceptance Criteria
- [ ] `docker compose -f deploy/docker-compose.smoke.yml config` parses cleanly (config-only validation; nothing is started)
- [ ] Exactly two services: `app` uses `image: apitest-app:smoke` with NO `build:` key anywhere in the file; `db` uses `postgres:16-alpine` with tmpfs-backed `/var/lib/postgresql/data` and the same pg_isready healthcheck shape as the base compose file
- [ ] Two networks `backend` and `probe`, BOTH declared `internal: true`; `app` attaches to both, `db` attaches to `backend` only
- [ ] NO `ports:` key anywhere; NO `/var/run/docker.sock` mount anywhere
- [ ] App hardening block present: non-root `user:`, `cap_drop: [ALL]`, `security_opt: ["no-new-privileges:true"]`, `read_only: true` with a tmpfs for `/tmp`, memory and pids limits, and env `PYTHONDONTWRITEBYTECODE: "1"`
- [ ] A commented `# runtime: runsc` line sits on the app service with a one-line note that flipping it on requires the attended runsc install (Rich's op)
- [ ] App env `DATABASE_URL: postgresql+asyncpg://postgres:test@db:5432/test`; `depends_on` db `condition: service_healthy`; app healthcheck mirrors the base file's curl-/health-database-connected shape
- [ ] The file header comments name the fences verbatim: project `apitest-smoke` only; never touches `apitest-f2`, `apitest-f2-cand`, or the standing :5433 suite database; the sandbox never builds images

## Implementation Notes
- Scaffolding task — a single compose YAML, no application code.
- Copy the db service shape from the base docker-compose.yml (it is already host-port-free and tmpfs-backed); the smoke file must stay standalone so a stray `docker compose up` in the repo root can never pick it up implicitly.
- The app container must still work read-only: uvicorn needs no writable paths besides /tmp; alembic upgrade runs at entrypoint and writes nothing to disk.
