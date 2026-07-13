#!/usr/bin/env python3
"""Run the DCL-derived outside-in assertions against the RUNNING api_test service.

DCL SPIKE, S3. Spec of record: dcl-factory-evaluation-2026-07.md §7 (re-aimed pass/kill).

Each assertion here is the mechanical output of a recorded rule in `derivation-rules.md`
(R1-R9) applied to `capability.dcl`. Every assertion carries, inline, the DCL block it
derives from and the rule/judgment-flags that produced it -- so a verifier can trace each
check back to a DCL line, which is the whole point of the spike (assertions DERIVED from the
spec, not hand-authored per stack).

Stdlib only (urllib) -- no third-party deps, no per-stack test framework, no glue: this
script hitting the live HTTP surface IS the "zero per-stack glue" claim made concrete.

Usage:  python3 run_derived_assertions.py [BASE_URL]
        BASE_URL defaults to http://localhost:8901 (the apitest-f2 compose deploy of record,
        docs/state/TASK-STAT-001/deploy-record-2026-07-12.yaml).
Exit:   0 iff every RUN assertion passed (SKIP/MISS do not fail the run; they are recorded).
"""

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone

BASE_URL = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8901").rstrip("/")
STATS = BASE_URL + "/stats"

results = []  # (id, rule, dcl_source, disposition, passed_or_None, detail)


def record(aid, rule, dcl_source, disposition, passed, detail):
    results.append((aid, rule, dcl_source, disposition, passed, detail))


def get_stats():
    """Invocation surface A-INTENT (R1 <- intent StatisticsQuery from Operator, empty shape).
    GET /stats, no body [J1: verb+path binding is judgment, not in the DCL]."""
    t0 = time.monotonic()
    req = urllib.request.Request(STATS, method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8")
        status = resp.status
    dt = time.monotonic() - t0
    return status, body, dt


def is_iso8601_utc(s):
    """UTC ISO-8601 check for A-FRA-FORMAT [J5: format is judgment-sourced, not DCL Text]."""
    if not isinstance(s, str):
        return False
    v = s.replace("Z", "+00:00") if s.endswith("Z") else s
    try:
        d = datetime.fromisoformat(v)
    except ValueError:
        return False
    return d.utcoffset() is not None and d.utcoffset().total_seconds() == 0


def main():
    print(f"# DCL-derived outside-in assertion run")
    print(f"# target: {STATS}")
    print(f"# started: {datetime.now(timezone.utc).isoformat()}")
    print()

    # --- Sample the live surface: two successive calls for the monotone/stability checks. ---
    try:
        status1, raw1, dt1 = get_stats()
        body1 = json.loads(raw1)
        status2, raw2, dt2 = get_stats()
        body2 = json.loads(raw2)
    except Exception as e:
        print(f"FATAL: could not reach {STATS}: {e}")
        sys.exit(3)

    print(f"# call 1: HTTP {status1} in {dt1*1000:.1f} ms -> {raw1}")
    print(f"# call 2: HTTP {status2} in {dt2*1000:.1f} ms -> {raw2}")
    print()

    # A-OUTCOME  (R2 <- outcome StatisticsReported; when { always StatisticsReported })  [J1,J2]
    record("A-OUTCOME", "R2",
           "outcome StatisticsReported (l.47); when always (l.64)",
           "RUN", status1 == 200,
           f"HTTP status = {status1} (expect 200 = success signal [J2])")

    # A-FIELD-SVC  (R3 <- event StatisticsProduced.service: Text required)  [J1,J3]
    svc = body1.get("service")
    record("A-FIELD-SVC", "R3",
           "event field service: Text required (l.30)",
           "RUN", isinstance(svc, str) and len(svc) > 0,
           f"service = {svc!r} (expect present, non-empty Text)")

    # A-FIELD-REQ  (R3 <- event StatisticsProduced.requestsServed: Number required)  [J1,J3,J4]
    rs = body1.get("requests_served")
    rs_present_numeric = isinstance(rs, (int, float)) and not isinstance(rs, bool)
    is_int = isinstance(rs, int) and not isinstance(rs, bool)
    record("A-FIELD-REQ", "R3",
           "event field requestsServed: Number required (l.31)",
           "RUN", rs_present_numeric,
           f"requests_served = {rs!r} (Number: {rs_present_numeric}; "
           f"integer [J4, beyond DCL]: {is_int})")

    # A-FIELD-FRA  (R3 <- event StatisticsProduced.firstRequestAt: Text required)  [J1,J3,J6]
    fra = body1.get("first_request_at", "___MISSING___")
    record("A-FIELD-FRA", "R3",
           "event field firstRequestAt: Text required (l.32)",
           "RUN", fra != "___MISSING___",
           f"first_request_at present = {fra != '___MISSING___'} "
           f"(value = {body1.get('first_request_at')!r}; required=presence, not non-null [J6])")

    # A-COUNT-MONO  (R4 <- observe ... count as statistics_reports / statistics_reported_total)  [J1,J7]
    mono = rs_present_numeric and isinstance(body2.get("requests_served"), (int, float)) \
        and body2["requests_served"] >= rs
    record("A-COUNT-MONO", "R4",
           "observe event/outcome count (l.59-60)",
           "RUN", mono,
           f"requests_served call1={rs} call2={body2.get('requests_served')} "
           f"(R4: non-decreasing; strict-increase is [J7, beyond DCL count])")

    # A-DURATION  (R5 <- observe capability duration as stats_report_duration)  [J1,J7]
    record("A-DURATION", "R5",
           "observe capability duration (l.58)",
           "RUN", dt1 < 5.0,
           f"latency = {dt1*1000:.1f} ms (< 5000 ms liveness bound [J7: bound not in DCL])")

    # A-LIFE-SERVING  (R6 <- lifecycle move Fresh to Serving on outcome StatisticsReported)  [J1,J6]
    fra1 = body1.get("first_request_at")
    record("A-LIFE-SERVING", "R6",
           "lifecycle move Fresh to Serving (l.74)",
           "RUN", fra1 is not None,
           f"Serving-state observable: first_request_at = {fra1!r} (non-null after a request)")

    # A-LIFE-STABLE  (R7 <- lifecycle end Serving)  [J1,J9]
    fra2 = body2.get("first_request_at")
    record("A-LIFE-STABLE", "R7",
           "lifecycle end Serving (l.73)",
           "RUN", fra1 == fra2 and fra1 is not None,
           f"first_request_at stable across calls: {fra1!r} == {fra2!r} "
           f"(immutability is [J9, read into terminal state])")

    # A-FRA-FORMAT  (R3 field + [J5] -- format is judgment-sourced, NOT pure DCL)  [J1,J3,J5]
    record("A-FRA-FORMAT", "R3+J5",
           "firstRequestAt: Text required (l.32) -- format from pass-bar/Request, not DCL",
           "RUN", is_iso8601_utc(fra1),
           f"first_request_at = {fra1!r} parses as UTC ISO-8601 = {is_iso8601_utc(fra1)} "
           f"[J5: DCL Text carries no format]")

    # A-AVAIL  (R8 <- policy StatisticsAvailability { availability dependency_tolerance allowed })  [J1,J8]
    record("A-AVAIL", "R8",
           "policy StatisticsAvailability governs capability (l.38-54)",
           "SKIP", None,
           "derivable in shape (with the DB down, GET /stats -> 200) but NOT runnable in the "
           "read-only HTTP venue: needs DB fault-injection [J8: policy names no dependency/fault "
           "surface]. Recorded, not executed.")

    # A-READONLY  (R9 <- NO rule block exists in capability.dcl)  -- MISS
    record("A-READONLY", "R9",
           "no rule block in capability.dcl",
           "MISS", None,
           "the Gherkin @negative scenario + pass-bar C-STATS-READONLY (POST /stats -> 405) has "
           "NO DCL construct to derive from -- capability.dcl declares zero rules. Flagship gap.")

    # --- Report -------------------------------------------------------------------------
    print("## Per-assertion results\n")
    run_pass = run_fail = skip = miss = 0
    for aid, rule, src, disp, passed, detail in results:
        if disp == "RUN":
            tag = "PASS" if passed else "FAIL"
            run_pass += int(bool(passed))
            run_fail += int(not passed)
        elif disp == "SKIP":
            tag = "SKIP"
            skip += 1
        else:
            tag = "MISS"
            miss += 1
        print(f"[{tag}] {aid:14s} ({rule:6s} <- {src})")
        print(f"       {detail}")
    print()
    total_run = run_pass + run_fail
    print(f"## Summary")
    print(f"RUN: {total_run}  (PASS {run_pass} / FAIL {run_fail})   SKIP: {skip}   MISS: {miss}")
    print(f"# finished: {datetime.now(timezone.utc).isoformat()}")
    sys.exit(0 if run_fail == 0 else 1)


if __name__ == "__main__":
    main()
