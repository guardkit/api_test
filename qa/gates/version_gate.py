#!/usr/bin/env python3
"""F4 VERSION gate — retro-registered for FEAT-B70F (C4-prep lane).

Grounds to the committed 007 spec features/version-endpoint/version-endpoint.feature:
GET /version returns a flat JSON object with EXACTLY the three lowercase keys
`version`, `commit`, `service`; version is a non-empty string; commit and service
exist as strings; the endpoint requires no auth; POST (and other mutating verbs)
are rejected 405 (read-only). Behaviour checks drive the LIVE deployed app on the
compose front door.

The EXACTLY-three-keys assertion is load-bearing: the spec pins the response shape
(no extra keys, flat, lowercase). Live caveat: the deployed container serves
commit:"unknown" (build-time metadata injection is a filed residue) — so this gate
asserts commit EXISTS and is a string, never that it equals a git hash.

Authored to the real live bytes (curl -si http://localhost:8901/version): the
response carries x-correlation-id and x-api-version, so both are asserted present.

F4 contract via _gatelib: exit 0 = pass; non-zero enumerates failures in the JSON
results envelope. Base URL from $API_TEST_BASE_URL (default http://localhost:8901).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _gatelib  # noqa: E402

GATE_ID = "version"
EXPECTED_FIELDS = {"version", "commit", "service"}


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


def main() -> None:
    base = (os.environ.get("API_TEST_BASE_URL") or "http://localhost:8901").rstrip("/")
    url = base + "/version"
    assertions: List[Dict[str, Any]] = []

    status, headers, body, err = _gatelib.http_get(url)
    post_status, post_err = _http_post(url)
    evidence = _gatelib._write_evidence(GATE_ID, {
        "url": url,
        "get": {"status": status, "headers": headers, "body": body,
                "error": str(err) if err else None},
        "post": {"status": post_status, "error": str(post_err) if post_err else None},
    })

    if err is not None:
        assertions.append({
            "id": f"{GATE_ID}::reachable", "status": "fail",
            "observed": f"request error: {err}",
            "expected": f"HTTP 200 from {url}", "evidence_ref": evidence,
        })
        _gatelib._emit_and_exit(assertions)

    assertions.append({
        "id": f"{GATE_ID}::status", "status": "pass" if status == 200 else "fail",
        "observed": str(status), "expected": "200", "evidence_ref": evidence,
    })

    for header in ("x-correlation-id", "x-api-version"):
        present = header in headers
        assertions.append({
            "id": f"{GATE_ID}::header::{header}",
            "status": "pass" if present else "fail",
            "observed": "present" if present else "absent",
            "expected": f"response header {header} present", "evidence_ref": evidence,
        })

    try:
        parsed = json.loads(body)
    except Exception:
        parsed = None
    body_ok = isinstance(parsed, dict)
    assertions.append({
        "id": f"{GATE_ID}::body_json", "status": "pass" if body_ok else "fail",
        "observed": "JSON object" if body_ok else "body not a JSON object",
        "expected": "JSON object body", "evidence_ref": evidence,
    })

    if body_ok:
        # Load-bearing: EXACTLY the three lowercase keys, nothing more, nothing less.
        fields_ok = set(parsed.keys()) == EXPECTED_FIELDS
        assertions.append({
            "id": f"{GATE_ID}::exact_fields", "status": "pass" if fields_ok else "fail",
            "observed": ",".join(sorted(parsed.keys())),
            "expected": "exactly: commit,service,version",
            "evidence_ref": evidence,
        })

        # Flat: no nested objects or arrays (spec: flat JSON, no nesting).
        flat_ok = all(not isinstance(v, (dict, list)) for v in parsed.values())
        assertions.append({
            "id": f"{GATE_ID}::flat", "status": "pass" if flat_ok else "fail",
            "observed": "flat" if flat_ok else "contains nested object/array",
            "expected": "flat JSON object (no nested objects or arrays)",
            "evidence_ref": evidence,
        })

        ver = parsed.get("version")
        ver_ok = isinstance(ver, str) and bool(ver)
        assertions.append({
            "id": f"{GATE_ID}::version_str", "status": "pass" if ver_ok else "fail",
            "observed": repr(ver), "expected": "version is a non-empty string",
            "evidence_ref": evidence,
        })

        # Live caveat: deployed container serves commit:"unknown" (filed residue) —
        # assert commit EXISTS and is a string, never that it equals a hash.
        commit = parsed.get("commit")
        commit_ok = isinstance(commit, str) and "commit" in parsed
        assertions.append({
            "id": f"{GATE_ID}::commit_str", "status": "pass" if commit_ok else "fail",
            "observed": repr(commit),
            "expected": "commit exists and is a string (value not asserted — build-metadata residue)",
            "evidence_ref": evidence,
        })

        svc = parsed.get("service")
        svc_ok = isinstance(svc, str) and "service" in parsed
        assertions.append({
            "id": f"{GATE_ID}::service_str", "status": "pass" if svc_ok else "fail",
            "observed": repr(svc), "expected": "service exists and is a string",
            "evidence_ref": evidence,
        })

    post_ok = post_status == 405
    assertions.append({
        "id": f"{GATE_ID}::post_rejected",
        "status": "pass" if post_ok else "fail",
        "observed": str(post_status),
        "expected": "405 (mutation rejected — /version is read-only)",
        "evidence_ref": evidence,
    })

    _gatelib._emit_and_exit(assertions)


if __name__ == "__main__":
    main()
