#!/usr/bin/env python3
"""F4 STATS gate — instantiated from feature_behaviour_gate.py (Factory-2 S3c).

Grounded to the originating request text (Mode P cid 2dfb4ef5): GET /stats returns
JSON with exactly `service` (configured app name), `requests_served` (process-lifetime
integer count of HTTP requests handled) and `first_request_at` (UTC ISO-8601, null until
a request has been handled; ASSUM-002: the in-flight statistics request counts itself).
Behaviour checks drive the LIVE deployed app: the counter moves between two calls, the
first-request time is stable, and the statistics are read-only (POST rejected).

F4 contract via _gatelib: exit 0 = pass; non-zero enumerates failures in the JSON
results envelope. Base URL from $API_TEST_BASE_URL (default http://localhost:8901).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _gatelib  # noqa: E402

GATE_ID = "stats"
EXPECTED_FIELDS = {"service", "requests_served", "first_request_at"}


def _http_post(url: str, timeout: float = 15.0) -> Tuple[Optional[int], Optional[Exception]]:
    req = urllib.request.Request(url, data=b"{}", method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, None
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception as exc:
        return None, exc


def _iso8601_ok(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except Exception:
        return False


def main() -> None:
    base = (os.environ.get("API_TEST_BASE_URL") or "http://localhost:8901").rstrip("/")
    url = base + "/stats"
    assertions: List[Dict[str, Any]] = []

    s1, h1, b1, e1 = _gatelib.http_get(url)
    s2, h2, b2, e2 = _gatelib.http_get(url)
    post_status, post_err = _http_post(url)
    evidence = _gatelib._write_evidence(GATE_ID, {
        "url": url,
        "first": {"status": s1, "headers": h1, "body": b1, "error": str(e1) if e1 else None},
        "second": {"status": s2, "headers": h2, "body": b2, "error": str(e2) if e2 else None},
        "post": {"status": post_status, "error": str(post_err) if post_err else None},
    })

    if e1 is not None or e2 is not None:
        assertions.append({
            "id": f"{GATE_ID}::reachable", "status": "fail",
            "observed": f"request error: {e1 or e2}",
            "expected": f"HTTP 200 from {url}", "evidence_ref": evidence,
        })
        _gatelib._emit_and_exit(assertions)

    assertions.append({
        "id": f"{GATE_ID}::status", "status": "pass" if s1 == 200 else "fail",
        "observed": str(s1), "expected": "200", "evidence_ref": evidence,
    })
    for header in ("x-correlation-id", "x-api-version"):
        present = header in h1
        assertions.append({
            "id": f"{GATE_ID}::header::{header}",
            "status": "pass" if present else "fail",
            "observed": "present" if present else "absent",
            "expected": f"response header {header} present", "evidence_ref": evidence,
        })

    try:
        j1, j2 = json.loads(b1), json.loads(b2)
    except Exception:
        j1, j2 = None, None
    body_ok = isinstance(j1, dict) and isinstance(j2, dict)
    assertions.append({
        "id": f"{GATE_ID}::body_json", "status": "pass" if body_ok else "fail",
        "observed": "JSON object" if body_ok else "body not a JSON object",
        "expected": "JSON object body", "evidence_ref": evidence,
    })

    if body_ok:
        fields_ok = set(j1.keys()) == EXPECTED_FIELDS
        assertions.append({
            "id": f"{GATE_ID}::exact_fields", "status": "pass" if fields_ok else "fail",
            "observed": ",".join(sorted(j1.keys())),
            "expected": "exactly: first_request_at,requests_served,service",
            "evidence_ref": evidence,
        })
        svc_ok = isinstance(j1.get("service"), str) and bool(j1.get("service"))
        assertions.append({
            "id": f"{GATE_ID}::service_str", "status": "pass" if svc_ok else "fail",
            "observed": repr(j1.get("service")), "expected": "service is a non-empty string",
            "evidence_ref": evidence,
        })
        c1, c2 = j1.get("requests_served"), j2.get("requests_served")
        ints_ok = all(isinstance(c, int) and not isinstance(c, bool) for c in (c1, c2))
        assertions.append({
            "id": f"{GATE_ID}::count_int", "status": "pass" if ints_ok else "fail",
            "observed": f"{c1!r}, {c2!r}", "expected": "requests_served is an integer",
            "evidence_ref": evidence,
        })
        counts_move = ints_ok and c2 > c1
        assertions.append({
            "id": f"{GATE_ID}::count_increases",
            "status": "pass" if counts_move else "fail",
            "observed": f"{c1!r} -> {c2!r}",
            "expected": "requests_served strictly increases across two calls",
            "evidence_ref": evidence,
        })
        f1, f2 = j1.get("first_request_at"), j2.get("first_request_at")
        # Live target has handled our first call by the time of the second:
        # per ASSUM-002 both must be non-null here, equal, and ISO-8601.
        first_ok = isinstance(f2, str) and _iso8601_ok(f2) and f1 == f2
        assertions.append({
            "id": f"{GATE_ID}::first_at_stable_iso",
            "status": "pass" if first_ok else "fail",
            "observed": f"{f1!r}, {f2!r}",
            "expected": "first_request_at non-null, stable across calls, UTC ISO-8601",
            "evidence_ref": evidence,
        })

    post_ok = post_status == 405
    assertions.append({
        "id": f"{GATE_ID}::post_rejected",
        "status": "pass" if post_ok else "fail",
        "observed": str(post_status),
        "expected": "405 (statistics are read-only)", "evidence_ref": evidence,
    })

    _gatelib._emit_and_exit(assertions)


if __name__ == "__main__":
    main()
