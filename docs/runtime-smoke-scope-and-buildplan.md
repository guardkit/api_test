# Runtime smoke — users round-trip in a sandboxed candidate · Scope + Build Plan
## For: /feature-spec → Rich's Gherkin review → /feature-plan → guardkit autobuild (shadow watching)
## Status: DRAFT for Rich's red-pen · 2026-07-25 · R5 feature 1 of the review-and-mission program
## Rulings embodied: ai-transition docs/software-factory-sandbox-options-card-2026-07-25.md (all five axes) + docs/software-factory-mission-statement-2026-07-25.md (moves M3: 0 → 1, and instruments M2)

## 1. What and why (one minute)

The factory's builds are verified by tests that can be mocked green — lpa FEAT-POC-006 was
Coach-approved with 345 tests and could not boot. This feature adds the layer that cannot be
faked: **deploy the freshly built app into a sandboxed throwaway environment, seed real data
into Postgres, call the running API over the network, and verify the seeded data round-trips**
— plus negative probes. It lands as an independent behavioural oracle at
`tests/acceptance/users_roundtrip.py`, which guardkit's existing oracle machinery
(`CoachValidator._produce_behavioural_oracle` → `_apply_behavioural_oracle_guard`) discovers by
convention and runs on every subsequent build of this repo. No guardkit changes are needed —
the seam exists and is null only because no repo has ever carried an oracle file.

**Honest expectation (Rich's, verbatim intent):** the Player may stub this. That outcome is
itself the test — the coach evidence, the shadow receipts, and the coordinator's own re-drive
of the oracle answer "did it stub?" honestly.

## 2. Deliverables (all in this repo; nothing else changes)

1. **`deploy/docker-compose.smoke.yml`** — a standalone throwaway stack, compose project
   `apitest-smoke`, never touching `apitest-f2` (live) or `apitest-f2-cand`:
   - app service from the **pre-built** image tag `apitest-app:smoke` (never `build:` inside
     the sandbox — builds need egress, the sandbox has none);
   - `postgres:16-alpine` with tmpfs data, no host port;
   - **two networks, both `internal: true`** (`backend`: app+db · `probe`: app+probe clients);
     **zero published ports anywhere**;
   - hardening on the app service: non-root user, `cap_drop: [ALL]`,
     `security_opt: [no-new-privileges:true]`, `read_only: true` + tmpfs scratch, memory/pids
     limits, no docker socket mount;
   - a commented `# runtime: runsc` line on the app service — flipped on the day Rich runs the
     attended two-minute runsc install (sudo is passworded; a Docker daemon restart is an
     attended op on the fleet host). The oracle is runtime-agnostic by design.
2. **`qa/smoke/seed.sql`** — deterministic seed rows carrying a per-run marker value the
   oracle generates, applied via `docker exec <db> psql` (no host port needed).
3. **`tests/acceptance/users_roundtrip.py`** — the oracle. Self-contained pytest, total budget
   under 300s (`GUARDKIT_ORACLE_TIMEOUT`), teardown ALWAYS (`down -v`, `finally:`):
   - ensure image: `docker build -t apitest-app:smoke .` on the HOST only if the tag is
     missing (host has egress; sandbox never builds);
   - `docker compose -p apitest-smoke -f deploy/docker-compose.smoke.yml up -d`; wait on the
     app container's own healthcheck via `docker inspect` (no host port to poll);
   - seed Postgres via `docker exec` psql with the run marker;
   - run probes from a **separate probe container** (`python:3.12-slim`, stdlib `urllib`
     only — no pip, zero egress) attached to the `probe` network, script bind-mounted
     read-only, emitting one JSON verdict on stdout;
   - assertions: (a) the DB-seeded marker row is visible through `GET /users` — a hardcoded
     response cannot know the run marker; (b) `POST /users` 201 → `GET /users/{id}` returns
     byte-equal fields; (c) `GET /users/<unknown-uuid>` → 404; (d) duplicate-email `POST` →
     409; (e) invalid-payload `POST` → 422;
   - pytest asserts on the probe's JSON verdict and prints it as evidence.
4. **`docs/runtime-smoke-scope-and-buildplan.md`** — this doc, Status Log kept current.

## 3. Binding constraints (the Player builds to these verbatim)

- The smoke stack is throwaway: unique project name `apitest-smoke`, `down -v` in a `finally`;
  a failed run must leave zero containers/networks/volumes behind.
- No published host ports in the smoke stack; no `/var/run/docker.sock` mounted into any smoke
  container; both networks `internal: true`.
- The probe script uses only the Python standard library.
- The oracle never touches the live compose project, the standing :5433 test Postgres, or
  `deploy/deploy.sh`'s candidate machinery — it is a sibling, not a replacement (the
  candidate-then-promote lane stays as ruled 07-17).
- Independence note, so the first bundle reads honestly: within THIS feature's own build the
  oracle is Player-authored and will be recorded `not_independent` — expected, not a defect.
  From the next merged feature onward it runs as independent evidence and populates
  `behavioural_oracle` in every bundle (M3: 0 → 1).

## 4. Command playbook (run in order; update the Status Log after each)

Context rationale: the smoke overlay + oracle wire into the deploy surface
(`docker-compose.yml`, `deploy/`), the API contract (`docs/API.md`, `src/main.py` routers),
and the sandbox rulings (the options card). The spec gets behaviour/contract docs; the plan
adds source files (playbook law 2).

```
/feature-spec "Runtime smoke: deploy the app into a sandboxed throwaway compose stack (pre-built image, internal-only zero-egress networks, hardened non-root app container), seed Postgres with a per-run marker, verify the seeded-data round-trip and POST→GET read-back plus 404/409/422 negative probes from an in-network stdlib probe container, as the independent behavioural oracle tests/acceptance/users_roundtrip.py per docs/runtime-smoke-scope-and-buildplan.md §2-§3" \
  --context docs/runtime-smoke-scope-and-buildplan.md \
  --context docs/API.md \
  --context docker-compose.yml \
  --context deploy/docker-compose.candidate.yml \
  --auto

/feature-plan "Runtime smoke oracle and sandboxed smoke stack (FEAT from spec above)" \
  --context features/<slug>/<slug>_summary.md \
  --context docs/runtime-smoke-scope-and-buildplan.md \
  --context docker-compose.yml \
  --context src/main.py \
  --context deploy/docker-compose.candidate.yml

guardkit autobuild feature FEAT-XXXX --verbose --max-turns 30
```

## 5. Done means

The oracle runs green by the coordinator's OWN hand (not just the Player's claim): fresh
`pytest tests/acceptance/users_roundtrip.py` from the repo root deploys, seeds, probes,
tears down, exits 0 inside 300s — twice in a row. The review-summary and the shadow receipts
(`qav_shadow_turn_N.json`) are read and reported honestly, including any stub attempt. M3
flips 0 → 1 only on that receipt, and M4 gains this build's shadow-judged verdicts.

## Status Log

| step | command | status | date | commit |
|---|---|---|---|---|
| scope+buildplan | this doc | DRAFT for red-pen | 2026-07-25 | — |
| TASK-SMOKE-003 | users round-trip oracle | implemented | 2026-07-25 | — |
| TASK-SMOKE-003 | debug: `.local` TLD → `.internal` | fixed | 2026-07-25 | — |
| TASK-SMOKE-003 | debug: seed SQL `NOW()` for timestamps | fixed | 2026-07-25 | — |
| TASK-SMOKE-003 | debug: `server_default` → Python `default` | fixed | 2026-07-25 | — |
| TASK-SMOKE-003 | debug: add `await db.commit()` to `create_user` | fixed | 2026-07-25 | — |
| TASK-SMOKE-003 | pytest green (all 5 checks) | PASS | 2026-07-25 | — |
