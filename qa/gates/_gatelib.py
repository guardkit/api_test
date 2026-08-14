"""Shared engine for api_test F4 gate scripts.

Implements the F4 gate-script CONTRACT
(guardkit/qa/formats/gate_registry.py): a gate prints a JSON object carrying an
``assertions`` list on stdout — each assertion ``{id, status, observed,
expected, evidence_ref}`` — and exits 0 iff every assertion passed; a non-zero
exit MUST enumerate its failing assertions. The live-gate executor parses that
envelope verbatim.

stdlib only (urllib) so a gate runs against the live compose deployment with no
extra dependencies. A gate is driven by a SPEC dict:

    {
      "gate_id": "health",
      "base_url_env": "API_TEST_BASE_URL",     # env-var NAME (LPA-02), not a URL
      "default_base_url": "http://localhost:8901",
      "request": {"method": "GET", "path": "/health"},
      "expect_status": 200,
      "headers_present": ["x-correlation-id", "x-api-version"],
      "json_assertions": [
        {"id": "health::db_connected", "path": "database", "equals": "connected"},
        {"id": "stats::count_is_int",  "path": "requests_served", "type": "int"},
        {"id": "stats::service_present","path": "service", "exists": true},
      ],
    }
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

EVIDENCE_DIR = Path("qa/gates/evidence")


def http_get(url: str, timeout: float = 15.0) -> Tuple[Optional[int], Dict[str, str], str, Optional[Exception]]:
    """GET ``url`` with stdlib. Returns (status, lowercased-headers, body, error)."""
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, headers, body, None
    except urllib.error.HTTPError as exc:  # a real HTTP response (4xx/5xx)
        body = exc.read().decode("utf-8", "replace") if exc.fp else ""
        headers = {k.lower(): v for k, v in (exc.headers.items() if exc.headers else [])}
        return exc.code, headers, body, None
    except Exception as exc:  # connection refused / DNS / timeout — not reachable
        return None, {}, "", exc


def _base_url(spec: Dict[str, Any]) -> str:
    env_name = spec.get("base_url_env", "API_TEST_BASE_URL")
    url = os.environ.get(env_name) or spec.get("default_base_url", "http://localhost:8901")
    return url.rstrip("/")


def _write_evidence(gate_id: str, payload: Dict[str, Any]) -> Optional[str]:
    try:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        path = EVIDENCE_DIR / f"{gate_id}_latest.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(path)
    except Exception:
        return None


def _emit_and_exit(assertions: List[Dict[str, Any]]) -> None:
    print(json.dumps({"assertions": assertions}))
    sys.exit(0 if all(a["status"] == "pass" for a in assertions) else 1)


def run_spec(spec: Dict[str, Any]) -> None:
    """Execute a gate SPEC against the live target and emit the F4 envelope."""
    gate_id = spec["gate_id"]
    url = _base_url(spec) + spec["request"]["path"]
    status, headers, body, err = http_get(url, spec.get("timeout", 15.0))
    evidence = _write_evidence(
        gate_id,
        {"url": url, "status": status, "headers": headers, "body": body,
         "error": str(err) if err else None},
    )
    assertions: List[Dict[str, Any]] = []

    # Not reachable at all => single honest failure (exit 1). Environment
    # attribution is pre-flight/F16's job; the gate reports the observed red.
    if err is not None:
        assertions.append({
            "id": f"{gate_id}::reachable",
            "status": "fail",
            "observed": f"request error: {err}",
            "expected": f"HTTP {spec.get('expect_status', 200)} from {url}",
            "evidence_ref": evidence,
        })
        _emit_and_exit(assertions)

    expect_status = spec.get("expect_status", 200)
    assertions.append({
        "id": f"{gate_id}::status",
        "status": "pass" if status == expect_status else "fail",
        "observed": str(status),
        "expected": str(expect_status),
        "evidence_ref": evidence,
    })

    for header in spec.get("headers_present", []):
        present = header.lower() in headers
        assertions.append({
            "id": f"{gate_id}::header::{header.lower()}",
            "status": "pass" if present else "fail",
            "observed": "present" if present else "absent",
            "expected": f"response header {header} present",
            "evidence_ref": evidence,
        })

    json_assertions = spec.get("json_assertions", [])
    parsed: Any = None
    if json_assertions:
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = None

    for ja in json_assertions:
        key = ja["path"]
        observed = parsed.get(key) if isinstance(parsed, dict) else None
        if "equals" in ja:
            ok = observed == ja["equals"]
            expected = f"{key} == {ja['equals']!r}"
        elif ja.get("type") == "int":
            ok = isinstance(observed, int) and not isinstance(observed, bool)
            expected = f"{key} is an integer"
        else:  # exists (default)
            ok = isinstance(parsed, dict) and key in parsed
            expected = f"{key} present in JSON body"
        assertions.append({
            "id": ja["id"],
            "status": "pass" if ok else "fail",
            "observed": repr(observed) if isinstance(parsed, dict) else "body not JSON",
            "expected": expected,
            "evidence_ref": evidence,
        })

    _emit_and_exit(assertions)
