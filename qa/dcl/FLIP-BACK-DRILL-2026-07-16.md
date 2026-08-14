# Flip-back drill + both-tracks proof — DCL spec track (Phase D / D3)

**Date:** 2026-07-16 · **Feature:** stats endpoint (`TASK-STAT-001` / `FEAT-AE43`)
**Spec:** `ai-transition/docs/dcl-adoption-phase-d-design-2026-07-16.md` §3 (D3).

## The one idea

DCL is an **optional spec track**. A repo says which track it is on in one line of
`.guardkit/config.yaml` (`qa.spec_track`). `gherkin` is the default and the permanent
fallback; `dcl` adds the derived, compiler-checked verification **on top of** the
untouched Gherkin chain.

## The drill law — flip-back is the kill switch

The single line `qa.spec_track: dcl` is the whole switch. **Deleting that line, or
setting it to `gherkin`, instantly and completely restores today's behaviour** — no code
change, no redeploy, no data migration. This drill proves that claim by walking the switch
through three states and verifying each one:

    dcl  →  gherkin  →  dcl        (resting state = dcl)

At every state we show the exact config change and run the verification that state calls
for. The fallback is proven, not asserted (design §0.1 Fallback law).

## Environment (all three states)

| Fact | Value |
|---|---|
| Repo | `api_test` |
| Branch | `ddd-demo` (never switched) |
| HEAD sha | `f6ba5817f730f6f7e40c679a111595fe6bd57b93` |
| Compose project | `apitest-f2` |
| Base URL (read-only HTTP) | `http://localhost:8901` |
| guardkit invocation | `uv run --no-sync` from `.../guardkit` (working tree serves the code) |
| Base-URL source | env var `API_TEST_BASE_URL` (LPA-02 — never hard-coded) |

Live surface is read-only HTTP; the closed-world assertions hit already-`405` mutating
verbs — no state risk.

---

## Both-tracks proof table (same feature, same live deploy)

| Evidence | `dcl` track | `gherkin` track (today) |
|---|---|---|
| `get_spec_track(api_test)` | `dcl` | `gherkin` |
| DCL oracle runs? | yes | **no** — guard `get_spec_track != "dcl"` returns `None` (agent_invoker.py:9172) |
| `guardkit dcl check` | exit 0, `COMPILE OK` | n/a (oracle inert) |
| `guardkit dcl derive` | exit 0, **13 RUN / 1 SKIP** | n/a |
| `guardkit dcl run` (live) | exit 0, **13/13 RUN PASS** | n/a |
| `local_live_gate` verdict | `pass` **with** `dcl-stats` (13 assertions) | `pass` **without** `dcl-stats` |
| gates exercised | health, stats, version, **dcl-stats** | health, stats, version |
| stats unit tests (`tests/test_stats.py`) | **19 passed** | **19 passed** (track-invariant) |

The unit tests are identical in both columns because the spec track touches no product
code — it only adds a verification lane. The Gherkin chain is byte-identical on both
tracks (the DCL paths are dead code when the track is `gherkin`).

---

## State 1 — `dcl` (the current / resting config)

**Config:** `qa.spec_track: dcl` (as committed).

**Track reader**

    $ uv run --no-sync python -c "...get_spec_track(Path('.../api_test'))"
    dcl                                                          # exit 0

**Compile gate**

    $ uv run --no-sync guardkit dcl check .../features/stats-endpoint/stats-endpoint.dcl
    ✓ COMPILE OK  (warnings: 0)                                  # exit 0

**Fresh derivation** (idempotent — the derived set re-derives byte-identical to the
committed `qa/dcl/derived/TASK-STAT-001.yaml`, sha `e6af4e5d…`)

    $ uv run --no-sync guardkit dcl derive --feature TASK-STAT-001 --repo .../api_test \
        --dcl .../features/stats-endpoint/stats-endpoint.dcl
    ✓ DERIVED TASK-STAT-001: 13 RUN / 1 SKIP                     # exit 0

**Run the derived assertions against live :8901** — the F4 gate envelope on stdout

    $ API_TEST_BASE_URL=http://localhost:8901 uv run --no-sync \
        guardkit dcl run --assertions .../qa/dcl/derived/TASK-STAT-001.yaml \
        --base-url-env API_TEST_BASE_URL
    # exit 0 — 13 assertions, all "pass". Verbatim samples:
    {"id":"A-OUTCOME",   "status":"pass","observed":"200",  "expected":"200",
       "evidence_ref":"R2 <- outcome StatisticsReported; when always StatisticsReported"}
    {"id":"A-FIELD-SVC", "status":"pass","observed":"'api'","expected":"non-empty Text",
       "evidence_ref":"R3 <- event StatisticsProduced field service: Text required"}
    {"id":"A-CW-DELETE", "status":"pass","observed":"405",  "expected":"400-499",
       "evidence_ref":"R10 <- closed-world over the intent set: only ['GET'] declared on /stats"}

**Full live-gate (all registered gates, `dcl-stats` included)**

    $ API_TEST_BASE_URL=http://localhost:8901 uv run --no-sync python \
        .../qa/gates/local_live_gate.py --feature TASK-STAT-001 --target local --repo .../api_test
    run_id:  TASK-STAT-001-local-20260716T185107Z              # exit 0
    verdict: pass
      health     exit=0  assertions=4
      stats      exit=0  assertions=10
      version    exit=0  assertions=10
      dcl-stats  exit=0  assertions=13

**Stats unit tests**

    $ DATABASE_URL=postgresql+asyncpg://postgres:test@localhost:5433/test \
        .venv/bin/python -m pytest tests/test_stats.py -q
    19 passed                                                    # exit 0

---

## State 2 — `gherkin` (the fallback / today)

**Config change** (the only edit — one line):

    -  spec_track: dcl
    +  spec_track: gherkin

**Track reader**

    $ uv run --no-sync python -c "...get_spec_track(Path('.../api_test'))"
    gherkin                                                      # exit 0

**The DCL oracle does not run** — reproducing the exact guard in
`AgentInvoker._run_dcl_oracle` (`guardkit/orchestrator/agent_invoker.py:9172`,
`if get_spec_track(self.worktree_path) != "dcl": return None`):

    track='gherkin' -> _run_dcl_oracle runs? False  (returns None / DCL oracle inert)
    PROVEN: DCL oracle does not run on the gherkin track

**Today-chain live-gate — the `dcl-stats` gate is NOT selected** (`health,stats,version`,
exactly the set that existed before Phase D):

    $ API_TEST_BASE_URL=http://localhost:8901 uv run --no-sync python \
        .../qa/gates/local_live_gate.py --feature TASK-STAT-001 --target local \
        --gates health,stats,version --repo .../api_test
    run_id:  TASK-STAT-001-local-20260716T185228Z              # exit 0
    verdict: pass
    gates run: ['health', 'stats', 'version']   dcl-stats present? False
      health   exit=0  assertions=4
      stats    exit=0  assertions=10
      version  exit=0  assertions=10

**Stats unit tests — unchanged, identical to State 1** (the two ledgered middleware reds
in `tests/test_middleware.py` are outside this targeted scope and are untouched by the
track, since no product code changes):

    $ DATABASE_URL=... .venv/bin/python -m pytest tests/test_stats.py -q
    19 passed                                                    # exit 0

---

## State 3 — `dcl` (flip back, resting state)

**Config change** (restore — `git diff .guardkit/config.yaml` is now empty, i.e. back to
the committed `dcl` line):

    -  spec_track: gherkin
    +  spec_track: dcl

**Track reader**

    $ uv run --no-sync python -c "...get_spec_track(Path('.../api_test'))"
    dcl                                                          # exit 0

**Full live-gate (all gates, `dcl-stats` back in)**

    $ API_TEST_BASE_URL=http://localhost:8901 uv run --no-sync python \
        .../qa/gates/local_live_gate.py --feature TASK-STAT-001 --target local --repo .../api_test
    run_id:  TASK-STAT-001-local-20260716T185252Z              # exit 0
    verdict: pass
      health     exit=0  assertions=4
      stats      exit=0  assertions=10
      version    exit=0  assertions=10
      dcl-stats  exit=0  assertions=13

The `dcl` state after the flip-back is indistinguishable from State 1 (same gate set, same
verdict, same 13 dcl-stats assertions). **The switch is fully reversible in both
directions.**

---

## Run-id / envelope index

| State | Track | Verification | run_id / receipt | Verdict |
|---|---|---|---|---|
| 1 | dcl | full live-gate (4 gates) | `TASK-STAT-001-local-20260716T185107Z` | pass |
| 1 | dcl | `guardkit dcl run` (F4 envelope) | 13/13 RUN pass, exit 0 | pass |
| 2 | gherkin | live-gate `health,stats,version` | `TASK-STAT-001-local-20260716T185228Z` | pass |
| 3 | dcl | full live-gate (4 gates) | `TASK-STAT-001-local-20260716T185252Z` | pass |

Live-gate run histories are written to `qa/gates/history/<run_id>.json` and per-gate
evidence to `qa/gates/evidence/<run_id>/`. Both trees are runtime artifacts (gitignored by
repo convention); the durable committed record is this receipt, which quotes the envelopes
verbatim above.

---

## Honest limits — what the `gherkin`-track green does and does NOT exercise

The `gherkin` proof shows two things and only two things:

1. **The switch reader flips** — `get_spec_track` returns `gherkin`, and the DCL oracle's
   own guard makes it inert (returns `None`), so nothing DCL runs.
2. **The today-chain still passes** — the stats unit tests are green (19/19) and the
   pre-Phase-D live gates (`health`, `stats`, `version`) pass with `dcl-stats` absent,
   byte-for-byte the behaviour before this lane existed.

What it does **not** exercise: the Gherkin `.feature` scenarios themselves are **not
executed by a wired BDD step-runner** in this repo today. `bdd_runner.py` discovers and
inventories the tagged scenarios, but there are no step definitions driving them against
the live app — they are **inert by design** (pre-existing gap **H-08**, unchanged by Phase
D). So "gherkin-track green" means "the today-chain behaves exactly as it did before" — it
does **not** mean "the Gherkin scenarios ran and passed". The Gherkin chain's role here is
the retained, untouched fallback contract, not an active executor; the actual outside-in
behavioural coverage on this feature comes from the F4 live gates (and, on the `dcl` track,
the 13 derived assertions). Poison-proofing that these gates fail LOUD on wrong inputs is
recorded separately in `qa/dcl/POISON-PROVE-dcl-stats-2026-07-16.md`.
