#!/usr/bin/env python3
"""ETag gate (FEAT-E613) — seeds its own user, then proves the two criteria.

The first dispatched candidate run (2026-08-25) proved the original
instantiation could never pass: it sent the literal placeholder
``/users/{user_id}`` (the server answered 400 "invalid characters"), and on a
fresh sandbox database there is no existing user to point at anyway. So this
gate now does what its pass-bar (qa/pass-bar-TASK-E613-001.yaml) actually
demands, end to end against a clean instance:

  AC-001  create a user, GET it, and the response carries an ETag header;
  AC-002  GET again with If-None-Match set to that ETag -> 304 with no body.

F4 contract via _gatelib: exit 0 = pass; non-zero enumerates the failing
assertions as the JSON results envelope. Base URL from $API_TEST_BASE_URL.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _gatelib  # noqa: E402

GATE_ID = "etag-generation-and-validation"
SPEC = {
    "gate_id": GATE_ID,
    "base_url_env": "API_TEST_BASE_URL",
    "default_base_url": "http://localhost:8901",
}


def _request(
    method: str,
    url: str,
    body: dict | None = None,
    headers: dict | None = None,
    timeout: float = 15.0,
):
    """(status, headers, body_text, error) — never raises."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return (
                resp.status,
                {k.lower(): v for k, v in resp.headers.items()},
                resp.read().decode("utf-8", "replace"),
                None,
            )
    except urllib.error.HTTPError as exc:
        return (
            exc.code,
            {k.lower(): v for k, v in exc.headers.items()},
            exc.read().decode("utf-8", "replace"),
            None,
        )
    except Exception as exc:  # noqa: BLE001 — the verdict reports it
        return None, {}, "", exc


def main() -> None:
    base = _gatelib._base_url(SPEC)
    assertions: list[dict] = []

    def add(aid: str, ok: bool, observed: str, expected: str) -> None:
        assertions.append(
            {
                "id": f"{GATE_ID}::{aid}",
                "status": "pass" if ok else "fail",
                "observed": observed[:300],
                "expected": expected,
            }
        )

    # Seed the subject: this gate owns its own data (a sandbox database
    # starts empty — pointing at a pre-existing user can never be assumed).
    email = f"etag-gate-{int(time.time())}-{os.getpid()}@example.com"
    status, _, body, err = _request(
        "POST", f"{base}/users", {"email": email, "full_name": "ETag Gate"}
    )
    if err is not None or status != 201:
        add(
            "seed-user",
            False,
            f"POST /users -> {status if err is None else err}",
            "201 (the gate creates the user it then reads)",
        )
        _gatelib._write_evidence(GATE_ID, {"assertions": assertions})
        _gatelib._emit_and_exit(assertions)
        return
    user_id = json.loads(body).get("id")
    add("seed-user", user_id is not None, f"created user {user_id}", "201 with an id")

    # AC-001: a standard GET returns an ETag header.
    status, headers, body, err = _request("GET", f"{base}/users/{user_id}")
    etag = headers.get("etag")
    add(
        "status",
        err is None and status == 200,
        str(status if err is None else err),
        "200",
    )
    for h in ("x-correlation-id", "x-api-version"):
        add(f"header::{h}", h in headers, "present" if h in headers else "absent",
            f"response header {h} present")
    add("etag-present", bool(etag), etag or "no ETag header", "an ETag header (AC-001)")

    # AC-002: If-None-Match with that ETag -> 304 and no body.
    if etag:
        status2, _, body2, err2 = _request(
            "GET", f"{base}/users/{user_id}", headers={"If-None-Match": etag}
        )
        add(
            "if-none-match-304",
            err2 is None and status2 == 304,
            str(status2 if err2 is None else err2),
            "304 on a matching If-None-Match (AC-002)",
        )
        add(
            "304-empty-body",
            err2 is None and not body2,
            f"{len(body2)} byte(s)",
            "an empty body with the 304",
        )

    _gatelib._write_evidence(
        GATE_ID,
        {"seeded_user_id": user_id, "etag": etag, "assertions": assertions},
    )
    _gatelib._emit_and_exit(assertions)


if __name__ == "__main__":
    main()
