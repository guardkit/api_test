---
complexity: 6
dependencies:
- TASK-SMOKE-001
- TASK-SMOKE-002
consumer_context:
- task: TASK-SMOKE-001
  consumes: SMOKE_COMPOSE_FILE
  framework: docker compose v2 (subprocess)
  driver: docker CLI
  format_note: Standalone file deploy/docker-compose.smoke.yml, project name apitest-smoke,
    services app+db, networks backend+probe both internal:true, app image apitest-app:smoke,
    no ports, no build key
- task: TASK-SMOKE-002
  consumes: PROBE_VERDICT_JSON
  framework: pytest (json.loads on captured stdout)
  driver: python:3.12-slim probe container
  format_note: 'Exactly one stdout line: {"pass": bool, "marker": str, "checks": [{"id",
    "pass", "detail"}...]}; exit 0 iff all checks pass'
status: in_review
autobuild_state:
  current_turn: 2
  max_turns: 30
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-8737
  base_branch: ddd-demo
  started_at: '2026-07-25T12:35:12.482671'
  last_updated: '2026-07-25T13:31:25.432156'
  turns:
  - turn: 1
    decision: feedback
    feedback: "- Runtime-parity failure: a test in the feature smoke suite FAILED\
      \ under this task's changes (exit=5, expected=0). The smoke command runs the\
      \ feature's test suite \u2014 fix the failing test(s) named in the output below.\
      \ Command: set -e\npython -m pytest tests/acceptance -x -q\n:\n  \n===============================\
      \ warnings summary ===============================\n.venv/lib/python3.11/site-packages/fastapi/testclient.py:1\n\
      \  /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-8737/.venv/lib/python3.11/site-packages/fastapi/testclient.py:1:\
      \ StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is\
      \ deprecated; install `httpx2` instead.\n    from starlette.testclient import\
      \ TestClient as TestClient  # noqa\n\n-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html\n\
      1 warning in 0.00s"
    timestamp: '2026-07-25T12:35:12.482671'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
  - turn: 2
    decision: approve
    feedback: null
    timestamp: '2026-07-25T13:19:40.198654'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
---

# Add users round-trip oracle

One new pytest file: `tests/acceptance/users_roundtrip.py` — the independent behavioural
oracle guardkit discovers by the `tests/acceptance/*_roundtrip.py` convention and runs on
every subsequent build of this repo. It orchestrates the whole smoke: ensure image → deploy
the sandboxed stack → wait healthy → seed with a per-run marker → run the in-network probe →
assert on its verdict → tear down unconditionally. Plus the Status Log row in the scope doc.
See docs/runtime-smoke-scope-and-buildplan.md §2.3, §3 (binding), and §5 (done bar).

## Acceptance Criteria
- [ ] `tests/acceptance/users_roundtrip.py` exists and `python -m pytest tests/acceptance/users_roundtrip.py -x -q` runs the full smoke green on this box, end to end, inside 300 seconds (cached-image case)
- [ ] Image step: `apitest-app:smoke` is built on the HOST via `docker build -t apitest-app:smoke .` ONLY when `docker image inspect apitest-app:smoke` fails; the sandbox never builds
- [ ] Deploy step: `docker compose -p apitest-smoke -f deploy/docker-compose.smoke.yml up -d` then wait for the app container's own healthcheck to report healthy via `docker inspect` polling, capped at 120 seconds — no host port is ever polled (none exists)
- [ ] Seed step: a fresh `uuid4().hex` marker is substituted for `__MARKER__` in `qa/smoke/seed.sql` and applied with `docker exec` + `psql -U postgres -d test` against the project's db container
- [ ] Probe step: the probe runs as `docker run --rm --network apitest-smoke_probe` from image `python:3.12-slim` with `qa/smoke/probe.py` bind-mounted read-only, env `APP_BASE_URL=http://app:8901` and `MARKER=<marker>`; stdout is captured and parsed as the PROBE_VERDICT_JSON contract; the test asserts `pass` is true and every check passed, printing the full verdict as evidence on failure
- [ ] Teardown ALWAYS: `docker compose -p apitest-smoke -f deploy/docker-compose.smoke.yml down -v --remove-orphans` runs in a `finally:` block; after any run (pass or fail) no `apitest-smoke` containers, networks, or volumes remain
- [ ] Docker unreachable is a loud FAILURE with a named reason, never a skip (a skip would read as a passing oracle — the exact fake-green channel this feature exists to close)
- [ ] The module never references project `apitest-f2`, `apitest-f2-cand`, or host port 5433; the project name lives in one constant `SMOKE_PROJECT = "apitest-smoke"`
- [ ] A new Status Log row is appended to `docs/runtime-smoke-scope-and-buildplan.md` recording this task's completion
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes
- Use `subprocess.run` with explicit timeouts on every docker invocation; accumulate elapsed time so the module respects the 300-second overall budget rather than discovering it at the guardkit runner's kill.
- The probe network's actual docker name is the compose project prefix plus the network key (`apitest-smoke_probe`) — derive it from `SMOKE_PROJECT` rather than hardcoding twice.
- `python:3.12-slim` is the app image's own base so it is present locally; do NOT pull explicitly (zero-egress discipline; a missing image should fail loudly with a named reason).
- Structure as a single test function plus small helpers in the same file; the file must be self-contained (guardkit runs it as `<worktree venv python> -m pytest <this file>` with a 300s timeout).
- Independence note (expected, not a defect): within THIS feature's own build the oracle is Player-authored, so the coach bundle will record `not_independent`. From the next merged feature onward it runs as independent evidence.