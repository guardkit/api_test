# Run receipt — DCL-derived outside-in assertions (DCL SPIKE, S3)

Verbatim receipt of `run_derived_assertions.py` executed against the **running** api_test service.
This is the conformance half of the spike: the DCL-derived assertions (each traced to a DCL block
by the recorded rules in `derivation-rules.md`) run outside-in against real running software — no
per-stack test framework, no step definitions, stdlib `urllib` only.

## Environment (reproduce)

- **Target service:** `http://localhost:8901` — the `apitest-f2` compose deployment of record
  (`docs/state/TASK-STAT-001/deploy-record-2026-07-12.yaml`; verdict bound to `a58bf31`,
  live-gate 14/14). Confirmed UP: `docker ps` → `apitest-f2-app-1 Up (healthy) 0.0.0.0:8901->8901`.
- **Runner:** `python3 run_derived_assertions.py` (Python **3.12.3**, stdlib only). No service
  was started or modified by this spike — read-only HTTP against the already-running deploy.
- **Command:** `cd qa/dcl-spike && python3 run_derived_assertions.py`
- **Exit code:** `0` (all RUN assertions passed).
- **Spec of record:** `dcl-factory-evaluation-2026-07.md` §7.

## Verbatim output (run at 2026-07-13T13:21:36Z)

```
# DCL-derived outside-in assertion run
# target: http://localhost:8901/stats
# started: 2026-07-13T13:21:36.270100+00:00

# call 1: HTTP 200 in 16.2 ms -> {"service":"api","requests_served":15988,"first_request_at":"2026-07-12T14:57:52.958536+00:00"}
# call 2: HTTP 200 in 2.1 ms -> {"service":"api","requests_served":15989,"first_request_at":"2026-07-12T14:57:52.958536+00:00"}

## Per-assertion results

[PASS] A-OUTCOME      (R2     <- outcome StatisticsReported (l.47); when always (l.64))
       HTTP status = 200 (expect 200 = success signal [J2])
[PASS] A-FIELD-SVC    (R3     <- event field service: Text required (l.30))
       service = 'api' (expect present, non-empty Text)
[PASS] A-FIELD-REQ    (R3     <- event field requestsServed: Number required (l.31))
       requests_served = 15988 (Number: True; integer [J4, beyond DCL]: True)
[PASS] A-FIELD-FRA    (R3     <- event field firstRequestAt: Text required (l.32))
       first_request_at present = True (value = '2026-07-12T14:57:52.958536+00:00'; required=presence, not non-null [J6])
[PASS] A-COUNT-MONO   (R4     <- observe event/outcome count (l.59-60))
       requests_served call1=15988 call2=15989 (R4: non-decreasing; strict-increase is [J7, beyond DCL count])
[PASS] A-DURATION     (R5     <- observe capability duration (l.58))
       latency = 16.2 ms (< 5000 ms liveness bound [J7: bound not in DCL])
[PASS] A-LIFE-SERVING (R6     <- lifecycle move Fresh to Serving (l.74))
       Serving-state observable: first_request_at = '2026-07-12T14:57:52.958536+00:00' (non-null after a request)
[PASS] A-LIFE-STABLE  (R7     <- lifecycle end Serving (l.73))
       first_request_at stable across calls: '2026-07-12T14:57:52.958536+00:00' == '2026-07-12T14:57:52.958536+00:00' (immutability is [J9, read into terminal state])
[PASS] A-FRA-FORMAT   (R3+J5  <- firstRequestAt: Text required (l.32) -- format from pass-bar/Request, not DCL)
       first_request_at = '2026-07-12T14:57:52.958536+00:00' parses as UTC ISO-8601 = True [J5: DCL Text carries no format]
[SKIP] A-AVAIL        (R8     <- policy StatisticsAvailability governs capability (l.38-54))
       derivable in shape (with the DB down, GET /stats -> 200) but NOT runnable in the read-only HTTP venue: needs DB fault-injection [J8: policy names no dependency/fault surface]. Recorded, not executed.
[MISS] A-READONLY     (R9     <- no rule block in capability.dcl)
       the Gherkin @negative scenario + pass-bar C-STATS-READONLY (POST /stats -> 405) has NO DCL construct to derive from -- capability.dcl declares zero rules. Flagship gap.

## Summary
RUN: 9  (PASS 9 / FAIL 0)   SKIP: 1   MISS: 1
# finished: 2026-07-13T13:21:36.288427+00:00
```

## Reading the receipt honestly

- **The counter provably moved:** `requests_served` 15988 → 15989 across the two successive GETs —
  A-COUNT-MONO is a real live observation, not a static field read.
- **9/9 RUN passed** — the DCL-derived assertions all hold against the running service. But the
  verdict is **not** "9/9 green"; it is what the derived set *covers* vs the Gherkin + pass-bar
  (see `coverage-crosscheck.md`). Two dispositions carry the real signal:
  - **A-AVAIL SKIP** — the availability policy *is* in the DCL and *is* derivable, but exercising it
    needs taking the DB down (fault-injection), which is outside the read-only HTTP venue and not
    safe against the shared deploy. Recorded as SKIP with reason, not silently dropped.
  - **A-READONLY MISS** — the read-only/mutation-rejection check (`POST /stats → 405`), which the
    Gherkin states as an explicit `@negative` scenario and the pass-bar as `C-STATS-READONLY`, has
    **no DCL construct to derive from** because `capability.dcl` declares zero `rule` blocks. This
    is the head-to-head's sharpest finding and is analysed in the cross-check.
- **No glue:** the runner is stdlib `urllib` + `json`. No pytest, no pytest-bdd, no step
  definitions, no conftest bridge, no per-language plugin. This is the "zero per-stack glue" PASS
  condition made concrete — contrast the Gherkin side's unpaid glue bill in `gherkin-glue-bill.md`.
