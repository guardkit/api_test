# Gherkin glue bill — the OTHER column of the head-to-head

**What would it cost, today, to make the three… (actually eight) `@task:TASK-STAT-001`
scenarios in `features/stats-endpoint/stats-endpoint.feature` actually EXECUTE?**

> **This is an ESTIMATE of UNBUILT work.** None of the glue below exists in api_test today —
> that is gap **H-08** ("the glue was never built"). The counts are grounded in the real
> guardkit BDD machinery (file:line receipts inline) and the real feature file, but no line
> of this glue has been written or run. Labelled honestly as a projection, not a receipt.

The handoff §0 calls the scenarios "three" (the original `@key-example` core); the feature
file as delivered carries **8 scenarios / 29 step lines** all tagged `@task:TASK-STAT-001`.
Both numbers are given below so the head-to-head is honest about scope.

---

## 0. Why none of it runs today (the starting hole)

Three independent preconditions are all currently UNMET:

| Precondition | State today | Receipt |
|---|---|---|
| `pytest-bdd` in api_test deps | **ABSENT** — deps are `pytest`, `pytest-asyncio`, `pytest-cov` only | `api_test/pyproject.toml` (no `pytest-bdd`) |
| `features/conftest.py` collection bridge | **ABSENT** | `features/` holds only `stats-endpoint/` + `uptime-endpoint/`, no `conftest.py` |
| glue module `test_stats_endpoint.py` | **ABSENT** | `features/stats-endpoint/` holds `.feature` + `_assumptions.yaml` + `_summary.md` only |

Consequence, from the real runner: with tagged `.feature` files present but `pytest-bdd`
not importable, `run_bdd_for_task` returns a **synthetic `pytest_bdd_not_importable`
failure** so Coach blocks (`bdd_runner.py:702-738`). Install `pytest-bdd` but leave the
bridge missing and pytest exits 4 "not found", which the runner treats as **absent /
not-applicable** — the scenarios silently do **not** run (`bdd_runner.py:773-803`;
`conftest_bridge.py:1-19`). So today the scenarios are inert: they verify nothing.

---

## 1. Step-definition functions — the bulk of the bill

pytest-bdd binds each `Given/When/Then/And` line to a Python step-definition function by its
parsed text. The feature has **29 step lines**; after de-duplicating repeated phrasings that
one function can serve, **22 distinct step definitions** must be authored:

**Given — 7 distinct** (the expensive ones — each needs real fixture/state machinery):
1. `the api_test service is running` — TestClient / app fixture (background, every scenario)
2. `I have requested the service statistics once` — call + stash prior response in context
3. `the service has handled at least one request`
4. `the service has just started and has handled no other requests` — **fresh app instance**
5. `I record the number of requests served` — stash a baseline in context
6. `the database is unavailable` — **stop/mock the DB** to prove `/stats` is independent of it
7. `the service restarts` — **restart the process / rebuild app** and re-establish the client

**When — 4 distinct** (3 are near-duplicate "request" verbs that a careful author collapses
with a pytest-bdd parser, but each still needs distinct capture logic — first vs. second vs.
two-in-a-row):
8. `I request the service statistics`
9. `I request the service statistics again`
10. `I request the service statistics twice`
11. `I attempt to submit changes to the service statistics` (POST — expect 405)

**Then / And — 11 distinct** (the assertions):
12. `the request should succeed`
13. `the response should include the configured service name`
14. `the response should include the number of requests served as a whole number`
15. `the response should include when the first request was handled` (reused by 2 scenarios — 1 def)
16. `the number of requests served should be higher than in the previous response`
17. `the reported first-request time should be identical in both responses`
18. `the reported first-request time should be in UTC ISO-8601 format`
19. `the number of requests served should be at least one`
20. `the number of requests served should not be lower than the recorded value`
21. `the request should be rejected as not allowed`
22. `the response should include the number of requests served`

**≈ 22 step-definition functions.** Three of the seven Givens (fresh instance, DB-unavailable,
restart) are not one-liners — they carry real fixture/lifecycle machinery and shared
step-to-step context (pytest-bdd `target_fixture` / a context object). Call it the largest,
least-mechanical part of the bill.

---

## 2. The conftest collection bridge — 1 file, ~151 lines (unbuilt here)

pytest-bdd v8 registers **no** `pytest_collect_file` hook for `.feature` files, so the
runner's invocation —
`pytest --gherkin-terminal-reporter --junitxml=… -m task_TASK_STAT_001 <path>.feature`
(`bdd_runner.py:558-584`) — exits 4 "not found" without a bridge. The canonical bridge
(`installer/core/templates/common/features/conftest.py.template`, **151 lines**) must sit at
`features/conftest.py`. It does two jobs (`conftest.py.template:1-49`): (a) redirect a
`.feature` argv to its sibling glue module `test_<slug>.py` (`:88`, `:137-150` — for this
feature, slug `stats-endpoint` → `test_stats_endpoint.py`), and (b) sanitise the Gherkin tag
`@task:TASK-STAT-001` → pytest marker `task_TASK_STAT_001` so the `-m` filter matches
(`:66-73`, `:108-116`). Normally auto-installed at worktree bootstrap
(`conftest_bridge.py:63-116`), but this repo's `features/` predates that and lacks it — so it
is on the bill.

---

## 3. pytest-bdd dependency + runner/marker wiring

- **Dependency add:** `pytest-bdd>=8.1,<9` into `api_test/pyproject.toml`, reinstall
  (`bdd_runner.py:716-721` names the exact pin in its remediation message).
- **Marker registration:** register `task_TASK_STAT_001` (and the tag family) under
  `[tool.pytest.ini_options] markers` to avoid `PytestUnknownMarkWarning`.
- **The glue's binding call:** `test_stats_endpoint.py` must invoke
  `scenarios("stats-endpoint.feature")` or per-scenario `@scenario(...)` decorators
  (`conftest.py.template:19-20`; the runner's binding markers `bdd_runner.py:895`).
- **Stack lock-in:** the runner is **pytest-only** — `_PYTEST_FRAMEWORKS =
  {"pytest", "pytest-bdd", "pytest_bdd"}` (`qa_seed.py:71`). This is the M-23 per-stack
  plugin burden: the same eight scenarios against a non-Python service would need that
  stack's own BDD runner + step-binding layer rebuilt from scratch — the in-process binding
  is the one irreducibly stack-specific step.

---

## 4. Ongoing (per-scenario) maintenance

- Every **new** scenario or **reworded** step line = a new or edited step-definition function
  (text-matched binding — a reworded `Then` silently becomes an *undefined* step: the
  authoring sweep counts it under `scenarios_undefined`, blocking — `bdd_runner.py:970-1153`).
- The three stateful Givens (fresh instance / DB-down / restart) carry fixtures that must be
  kept working as the app evolves.
- pending-vs-failed three-state bookkeeping is handled by the runner, but a genuine reword
  that desyncs glue from feature shows up as a Coach block until the glue is chased.

---

## 5. Headline numbers (the column to place beside the DCL cost)

| Line item | Count / size | Built today? |
|---|---|---|
| Step-definition functions | **≈ 22** (from 29 step lines, 8 scenarios) | ✗ none |
| — of which non-trivial fixtures | 3 Givens (fresh / DB-down / restart) | ✗ |
| Collection bridge `features/conftest.py` | 1 file, **~151 lines** | ✗ absent |
| glue module `test_stats_endpoint.py` | 1 file (22 defs + `scenarios()` bind) | ✗ absent |
| `pytest-bdd` dependency | 1 dep add + reinstall | ✗ absent |
| Marker/runner wiring | markers entry + binding call | ✗ |
| Per-stack runner (M-23) | rebuilt per non-Python target | pytest-only (`qa_seed.py:71`) |
| **Ongoing** | new/edited step def **per** added-or-reworded scenario | — |

**Contrast anchor for the results table:** the DCL side authored the whole `/stats`
capability spec in **1 file, 38 non-comment lines, 2 compile iterations, 2m35s to a green
compiler gate, and zero step-definition / bridge / dependency glue** (see `capability.dcl` +
`compile-log.md`). The honest counter-weight the results table must also carry: the DCL spec
does **not**, by itself, *execute* anything — S3 tests whether outside-in assertions can be
*derived* from it without re-incurring a step-definition-scale bill of their own. This bill is
the "what BDD execution costs" column; S3 produces the "what DCL-derived execution costs"
column.
