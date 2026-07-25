"""In-network smoke probe for the users API.

Runs inside a sandbox with only the Python standard library available.
Reads APP_BASE_URL and MARKER from the environment and performs five
behavioural checks against the running service.

Verdict output (single JSON line to stdout):
    {"pass": bool, "marker": str,
     "checks": [{"id": str, "pass": bool, "detail": str}, ...]}

All diagnostic chatter goes to stderr.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from typing import cast
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Configuration -- read lazily so the module is importable without env vars
# ---------------------------------------------------------------------------

_TIMEOUT: int = 5  # seconds per HTTP call


def _app_base_url() -> str:
    """Return APP_BASE_URL from environment."""
    return os.environ["APP_BASE_URL"]


def _marker() -> str:
    """Return MARKER from environment."""
    return os.environ["MARKER"]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _request(
    method: str, path: str, body: object | None = None
) -> tuple[int, dict[str, object]]:
    """Send an HTTP request and return (status_code, parsed_json_body).

    Raises HTTPError for 4xx/5xx responses -- the caller inspects the status.
    """
    base = _app_base_url()
    url = f"{base.rstrip('/')}/{path.lstrip('/')}"
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    resp = urlopen(req, timeout=_TIMEOUT)  # noqa: S310
    return resp.status, json.loads(resp.read().decode("utf-8"))


def _get(path: str) -> tuple[int, dict[str, object]]:
    """GET helper."""
    return _request("GET", path)


def _post(path: str, body: object) -> tuple[int, dict[str, object]]:
    """POST helper."""
    return _request("POST", path, body)


# ---------------------------------------------------------------------------
# Check functions -- each returns (check_id, passed: bool, detail: str)
# ---------------------------------------------------------------------------


def check_user_list_contains_marker() -> tuple[str, bool, str]:
    """Check 1: the user listing contains the seeded marker row."""
    marker = _marker()
    try:
        status, data = _get("/users")
        if status != 200:
            return ("user_list_contains_marker", False, f"GET /users returned {status}")
        items = cast(list[dict[str, object]], data.get("items", []))
        for item in items:
            email = item.get("email", "")
            pattern = f"seeded-{marker}@smoke.local"
            if email == pattern:
                return (
                    "user_list_contains_marker",
                    True,
                    "Seeded marker row found in user list",
                )
        return (
            "user_list_contains_marker",
            False,
            f"Marker '{marker}' not found in user list",
        )
    except HTTPError as exc:
        return ("user_list_contains_marker", False, f"GET /users HTTPError: {exc.code}")
    except OSError as exc:
        return ("user_list_contains_marker", False, f"GET /users network error: {exc}")


def check_created_user_fetch() -> tuple[str, bool, str]:
    """Check 2: created user fetched back has identical email and full_name."""
    marker = _marker()
    test_email = f"probe-{marker}@test.local"
    test_name = f"Probe User {marker}"
    try:
        # Create the user
        status, created = _post("/users", {"email": test_email, "full_name": test_name})
        if status != 201:
            return (
                "created_user_fetch",
                False,
                f"POST /users returned {status}: {created}",
            )
        user_id = created.get("id")
        if not user_id:
            return ("created_user_fetch", False, "POST /users did not return an id")
        # Fetch it back
        status2, fetched = _get(f"/users/{user_id}")
        if status2 != 200:
            return (
                "created_user_fetch",
                False,
                f"GET /users/{user_id} returned {status2}",
            )
        if fetched.get("email") != test_email:
            return (
                "created_user_fetch",
                False,
                f"Email mismatch: {fetched.get('email')}",
            )
        if fetched.get("full_name") != test_name:
            return (
                "created_user_fetch",
                False,
                f"Full name mismatch: {fetched.get('full_name')}",
            )
        return (
            "created_user_fetch",
            True,
            "Created user fetched back with matching fields",
        )
    except HTTPError as exc:
        return ("created_user_fetch", False, f"HTTPError: {exc.code}")
    except OSError as exc:
        return ("created_user_fetch", False, f"Network error: {exc}")


def check_random_id_not_found() -> tuple[str, bool, str]:
    """Check 3: looking up a random never-created id reports not-found."""
    fake_id = str(uuid.uuid4())
    try:
        status, data = _get(f"/users/{fake_id}")
        if status == 404:
            return ("random_id_not_found", True, f"GET /users/{fake_id} returned 404")
        return ("random_id_not_found", False, f"Expected 404, got {status}")
    except HTTPError as exc:
        if exc.code == 404:
            return ("random_id_not_found", True, f"GET /users/{fake_id} returned 404")
        return ("random_id_not_found", False, f"Unexpected HTTPError: {exc.code}")
    except OSError as exc:
        return ("random_id_not_found", False, f"Network error: {exc}")


def check_duplicate_email_conflict() -> tuple[str, bool, str]:
    """Check 4: re-creating the same email reports a conflict."""
    marker = _marker()
    test_email = f"probe-{marker}@test.local"
    try:
        status, data = _post("/users", {"email": test_email, "full_name": "Duplicate"})
        if status == 409:
            return (
                "duplicate_email_conflict",
                True,
                "POST /users returned 409 conflict",
            )
        return (
            "duplicate_email_conflict",
            False,
            f"Expected 409, got {status}: {data}",
        )
    except HTTPError as exc:
        if exc.code == 409:
            return (
                "duplicate_email_conflict",
                True,
                "POST /users returned 409 conflict",
            )
        return ("duplicate_email_conflict", False, f"Unexpected HTTPError: {exc.code}")
    except OSError as exc:
        return ("duplicate_email_conflict", False, f"Network error: {exc}")


def check_malformed_submission_validation_failure() -> tuple[str, bool, str]:
    """Check 5: malformed submission reports validation failure."""
    try:
        # Send invalid email
        status, data = _post("/users", {"email": "not-an-email", "full_name": "Bad"})
        if status == 422:
            return (
                "malformed_submission",
                True,
                "POST /users returned 422 validation error",
            )
        return ("malformed_submission", False, f"Expected 422, got {status}: {data}")
    except HTTPError as exc:
        if exc.code == 422:
            return (
                "malformed_submission",
                True,
                "POST /users returned 422 validation error",
            )
        return ("malformed_submission", False, f"Unexpected HTTPError: {exc.code}")
    except OSError as exc:
        return ("malformed_submission", False, f"Network error: {exc}")


# ---------------------------------------------------------------------------
# Verdict assembly
# ---------------------------------------------------------------------------


def run_all_checks() -> list[dict[str, object]]:
    """Run all five checks and return the list of check result dicts."""
    checks = [
        check_user_list_contains_marker(),
        check_created_user_fetch(),
        check_random_id_not_found(),
        check_duplicate_email_conflict(),
        check_malformed_submission_validation_failure(),
    ]
    return [
        {"id": cid, "pass": passed, "detail": detail} for cid, passed, detail in checks
    ]


def verdict_json(checks: list[dict[str, object]], marker: str | None = None) -> str:
    """Build the single-line verdict JSON."""
    if marker is None:
        marker = _marker()
    all_pass = all(c["pass"] for c in checks)
    return json.dumps({"pass": all_pass, "marker": marker, "checks": checks})


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the probe and emit verdict JSON to stdout."""
    marker = _marker()
    checks = run_all_checks()
    print(verdict_json(checks, marker=marker), flush=True)  # stdout
    # Diagnostic output goes to stderr
    for c in checks:
        status = "PASS" if c["pass"] else "FAIL"
        print(f"[{status}] {c['id']}: {c['detail']}", file=sys.stderr)

    all_pass = all(c["pass"] for c in checks)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
