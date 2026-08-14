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
status: blocked
autobuild_state:
  current_turn: 3
  max_turns: 30
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-8737
  base_branch: ddd-demo
  started_at: '2026-07-25T11:40:20.763325'
  last_updated: '2026-07-25T11:40:22.136037'
  turns:
  - turn: 1
    decision: feedback
    feedback: "- Direct-mode evidence gate blocked the turn (direct_mode_ac_unverified).\
      \ Direct mode relaxes coverage/arch gates but still requires verifiable AC delivery,\
      \ resolved wiring, and runnable registered producers:\n- [direct_mode_ac_unverified]\
      \ Direct mode: 7/7 acceptance criteria have no disk evidence (unmet: ['AC-001',\
      \ 'AC-002', 'AC-003', 'AC-004', 'AC-005', 'AC-006', 'AC-007']). Direct mode\
      \ relaxes coverage/arch but NOT AC delivery.\n\n[Command Execution Advisory]\n\
      - Command `docker compose -f deploy/docker-compose.smoke.yml config` failed\
      \ (unknown (may be implementation-related)):\n  open /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-8737/deploy/docker-compose.smoke.yml:\
      \ no such file or directory"
    timestamp: '2026-07-25T11:40:20.763325'
    player_summary: '[RECOVERED via player_report] Original error: Unexpected error:
      SDK invocation failed for player (LangGraphHarnessError): LangGraphHarness:
      failed to construct DeepAgent for role=''player'' model=''openai:claude-sonnet-4-5-20250929'':
      Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`,
      or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable.'
    player_success: true
    coach_success: true
  - turn: 2
    decision: feedback
    feedback: "- Direct-mode evidence gate blocked the turn (direct_mode_ac_unverified).\
      \ Direct mode relaxes coverage/arch gates but still requires verifiable AC delivery,\
      \ resolved wiring, and runnable registered producers:\n- [direct_mode_ac_unverified]\
      \ Direct mode: 7/7 acceptance criteria have no disk evidence (unmet: ['AC-001',\
      \ 'AC-002', 'AC-003', 'AC-004', 'AC-005', 'AC-006', 'AC-007']). Direct mode\
      \ relaxes coverage/arch but NOT AC delivery.\n\n[Command Execution Advisory]\n\
      - Command `docker compose -f deploy/docker-compose.smoke.yml config` failed\
      \ (unknown (may be implementation-related)):\n  open /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-8737/deploy/docker-compose.smoke.yml:\
      \ no such file or directory"
    timestamp: '2026-07-25T11:40:21.462151'
    player_summary: '[RECOVERED via player_report] Original error: Unexpected error:
      SDK invocation failed for player (LangGraphHarnessError): LangGraphHarness:
      failed to construct DeepAgent for role=''player'' model=''openai:claude-sonnet-4-5-20250929'':
      Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`,
      or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable.'
    player_success: true
    coach_success: true
  - turn: 3
    decision: feedback
    feedback: "- Direct-mode evidence gate blocked the turn (direct_mode_ac_unverified).\
      \ Direct mode relaxes coverage/arch gates but still requires verifiable AC delivery,\
      \ resolved wiring, and runnable registered producers:\n- [direct_mode_ac_unverified]\
      \ Direct mode: 7/7 acceptance criteria have no disk evidence (unmet: ['AC-001',\
      \ 'AC-002', 'AC-003', 'AC-004', 'AC-005', 'AC-006', 'AC-007']). Direct mode\
      \ relaxes coverage/arch but NOT AC delivery.\n\n[Command Execution Advisory]\n\
      - Command `docker compose -f deploy/docker-compose.smoke.yml config` failed\
      \ (unknown (may be implementation-related)):\n  open /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-8737/deploy/docker-compose.smoke.yml:\
      \ no such file or directory"
    timestamp: '2026-07-25T11:40:21.806786'
    player_summary: '[RECOVERED via player_report] Original error: Unexpected error:
      SDK invocation failed for player (LangGraphHarnessError): LangGraphHarness:
      failed to construct DeepAgent for role=''player'' model=''openai:claude-sonnet-4-5-20250929'':
      Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`,
      or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable.'
    player_success: true
    coach_success: true
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
