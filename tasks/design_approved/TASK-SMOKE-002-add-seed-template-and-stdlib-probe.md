---
autobuild_state:
  base_branch: ddd-demo
  current_turn: 3
  last_updated: '2026-07-25T11:40:22.214578'
  max_turns: 30
  started_at: '2026-07-25T11:40:20.770817'
  turns:
  - coach_success: true
    decision: feedback
    feedback: '- Direct-mode evidence gate blocked the turn (direct_mode_ac_unverified).
      Direct mode relaxes coverage/arch gates but still requires verifiable AC delivery,
      resolved wiring, and runnable registered producers:

      - [direct_mode_ac_unverified] Direct mode: 6/6 acceptance criteria have no disk
      evidence (unmet: [''AC-001'', ''AC-002'', ''AC-003'', ''AC-004'', ''AC-005'',
      ''AC-006'']). Direct mode relaxes coverage/arch but NOT AC delivery.'
    player_success: true
    player_summary: '[RECOVERED via git_only] Original error: Unexpected error executing
      task-work: LangGraphHarness: failed to construct DeepAgent for role=''player''
      model=''openai:claude-sonnet-4-5-20250929'': Missing credentials. Please pass
      an `api_key`, `workload_identity`, `admin_api_key`, or set the `OPENAI_API_KEY`
      or `OPENAI_ADMIN_KEY` environment variable.'
    timestamp: '2026-07-25T11:40:20.770817'
    turn: 1
  - coach_success: true
    decision: feedback
    feedback: '- Direct-mode evidence gate blocked the turn (direct_mode_ac_unverified).
      Direct mode relaxes coverage/arch gates but still requires verifiable AC delivery,
      resolved wiring, and runnable registered producers:

      - [direct_mode_ac_unverified] Direct mode: 6/6 acceptance criteria have no disk
      evidence (unmet: [''AC-001'', ''AC-002'', ''AC-003'', ''AC-004'', ''AC-005'',
      ''AC-006'']). Direct mode relaxes coverage/arch but NOT AC delivery.'
    player_success: true
    player_summary: '[RECOVERED via git_only] Original error: Unexpected error executing
      task-work: LangGraphHarness: failed to construct DeepAgent for role=''player''
      model=''openai:claude-sonnet-4-5-20250929'': Missing credentials. Please pass
      an `api_key`, `workload_identity`, `admin_api_key`, or set the `OPENAI_API_KEY`
      or `OPENAI_ADMIN_KEY` environment variable.'
    timestamp: '2026-07-25T11:40:21.568208'
    turn: 2
  - coach_success: false
    decision: error
    feedback: null
    player_success: false
    player_summary: 'Unexpected error executing task-work: LangGraphHarness: failed
      to construct DeepAgent for role=''player'' model=''openai:claude-sonnet-4-5-20250929'':
      Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`,
      or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable.'
    timestamp: '2026-07-25T11:40:22.068002'
    turn: 3
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-8737
complexity: 4
dependencies: []
feature_id: FEAT-8737
id: TASK-SMOKE-002
implementation_mode: task-work
parent_review: TASK-REV-RSMK
status: design_approved
task_type: feature
title: Add seed template and stdlib probe
wave: 1
---

# Add seed template and stdlib probe

Two new files under `qa/smoke/`: the Postgres seed template and the in-network probe script.
The probe is the examiner that runs INSIDE the sandbox's probe network from a stock
`python:3.12-slim` container with zero egress — so it may import ONLY the Python standard
library (no pip installs are possible where it runs). See
docs/runtime-smoke-scope-and-buildplan.md §2.2–§2.3 and §3 (binding).

## Acceptance Criteria
- [ ] `qa/smoke/seed.sql` inserts exactly ONE row into `users` providing explicit `id`, `email`, `full_name`, `is_active` values, with the literal token `__MARKER__` appearing in both the email (shape: `seeded-__MARKER__@smoke.local`) and the full name; a header comment states the oracle substitutes `__MARKER__` per run
- [ ] `qa/smoke/probe.py` imports only Python standard-library modules (no third-party imports anywhere in the file)
- [ ] `probe.py` reads `APP_BASE_URL` and `MARKER` from the environment and performs five checks against the running service: (1) the user listing contains the seeded marker row; (2) a created user fetched back by its returned id has identical email and full name; (3) looking up a random never-created id reports not-found; (4) re-creating the same email reports a conflict; (5) a malformed submission (invalid email, missing fields) reports a validation failure and creates nothing
- [ ] `probe.py` prints exactly ONE line of JSON to stdout: `{"pass": bool, "marker": str, "checks": [{"id": str, "pass": bool, "detail": str}, ...]}` and exits 0 when all checks pass, 1 otherwise; all diagnostic chatter goes to stderr
- [ ] Unit tests (in-process, no docker, no network — hermetic) cover: the stdlib-only import rule (walk the module's AST and assert every top-level import is stdlib), the verdict JSON shape, and the check-aggregation logic (all-pass → pass true; any-fail → pass false)
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes
- Keep probe.py runnable as `python /probe.py` with no arguments — configuration comes only from the two environment variables.
- Use `urllib.request` with explicit timeouts (a hung endpoint must not hang the probe past its share of the oracle budget); catch `HTTPError` to read 4xx statuses without raising.
- The not-found probe id must be a freshly generated UUID string, not a hardcoded one.
- Do not implement any docker orchestration here — that is TASK-SMOKE-003's job. This task's tests exercise probe logic hermetically (e.g. monkeypatched urlopen), never a live stack.

## Seam Tests

The following seam test validates the integration contract with the consumer task. The
verdict JSON is the boundary artifact TASK-SMOKE-003 parses.

```python
"""Seam test: verify PROBE_VERDICT_JSON contract for TASK-SMOKE-003."""
import json
import subprocess
import sys

import pytest


@pytest.mark.seam
def test_probe_verdict_json_is_single_parseable_line(monkeypatch):
    """Verify probe.py emits exactly one stdout line of contract-shaped JSON.

    Contract: {"pass": bool, "marker": str, "checks": [{"id", "pass", "detail"}...]}
    Producer: TASK-SMOKE-002 (qa/smoke/probe.py)
    Consumer: TASK-SMOKE-003 (tests/acceptance/users_roundtrip.py)
    """
    # Drive probe.py in a mode where all HTTP is stubbed to fail fast
    # (unreachable APP_BASE_URL + tiny timeout); the verdict must still be
    # exactly one JSON line on stdout with the contract keys.
    result = subprocess.run(
        [sys.executable, "qa/smoke/probe.py"],
        env={"APP_BASE_URL": "http://127.0.0.1:1", "MARKER": "seamtest"},
        capture_output=True, text=True, timeout=60,
    )
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    assert len(lines) == 1, f"expected exactly one stdout line, got {len(lines)}"
    verdict = json.loads(lines[0])
    assert set(verdict) == {"pass", "marker", "checks"}
    assert verdict["pass"] is False and verdict["marker"] == "seamtest"
    assert all({"id", "pass", "detail"} <= set(c) for c in verdict["checks"])
```