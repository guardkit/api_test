"""Users round-trip oracle for the runtime smoke test.

Orchestrates the full smoke lifecycle:
  1. Ensure ``apitest-app:smoke`` image exists (build on host if missing).
  2. Deploy the sandboxed stack via docker-compose.
  3. Wait for the app container healthcheck to report healthy.
  4. Seed Postgres with a per-run ``uuid4().hex`` marker.
  5. Run the in-network probe (``qa/smoke/probe.py``) and assert on its verdict.
  6. Teardown unconditionally in a ``finally`` block.

The module never references ``apitest-f2``, ``apitest-f2-cand``, or host port
5433.  Docker-unreachable is a loud FAILURE (never a skip).

Usage::

    python -m pytest tests/acceptance/users_roundtrip.py -x -q

Total budget: 300 seconds.
"""

from __future__ import annotations

import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Constants — single source of truth for project identity
# ---------------------------------------------------------------------------

SMOKE_PROJECT = "apitest-smoke"
COMPOSE_FILE = Path("deploy/docker-compose.smoke.yml")
SEED_SQL = Path("qa/smoke/seed.sql")
PROBE_SCRIPT = Path("qa/smoke/probe.py")
WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent  # repo root
OVERALL_TIMEOUT = 300  # seconds
IMAGE_BUILD_TIMEOUT = 120  # seconds
HEALTH_POLL_INTERVAL = 3  # seconds
HEALTH_POLL_TIMEOUT = 120  # seconds
DOCKER_EXEC_TIMEOUT = 30  # seconds
PROBE_TIMEOUT = 60  # seconds

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _elapsed(start: float) -> float:
    """Return elapsed seconds since *start*."""
    return time.monotonic() - start


def _check_budget(start: float) -> None:
    """Raise ``pytest.skip`` if the overall budget is exceeded.

    This is a last-resort guard; the caller should check before each step.
    """
    if _elapsed(start) >= OVERALL_TIMEOUT:
        pytest.fail(
            f"Overall timeout of {OVERALL_TIMEOUT}s exceeded "
            f"({_elapsed(start):.1f}s elapsed)"
        )


def _docker_available() -> bool:
    """Return ``True`` if the Docker daemon is reachable."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _ensure_image(start: float) -> None:
    """Build ``apitest-app:smoke`` on the host only if the tag is missing."""
    _check_budget(start)

    inspect = subprocess.run(
        ["docker", "image", "inspect", "apitest-app:smoke"],
        capture_output=True,
        timeout=15,
        check=False,
    )
    if inspect.returncode == 0:
        return  # Image already present

    result = subprocess.run(
        ["docker", "build", "-t", "apitest-app:smoke", "."],
        capture_output=True,
        timeout=IMAGE_BUILD_TIMEOUT,
        check=False,
        cwd=str(WORKTREE_ROOT),
    )
    if result.returncode != 0:
        stderr = (result.stderr or b"").decode("utf-8", errors="replace")
        pytest.fail(f"docker build failed (exit {result.returncode}):\n{stderr}")


def _deploy_stack(start: float) -> None:
    """Bring up the smoke stack and wait for app healthcheck."""
    _check_budget(start)

    compose_cmd = [
        "docker",
        "compose",
        "-p",
        SMOKE_PROJECT,
        "-f",
        str(COMPOSE_FILE),
        "up",
        "-d",
    ]
    result = subprocess.run(
        compose_cmd,
        capture_output=True,
        timeout=60,
        check=False,
        cwd=str(WORKTREE_ROOT),
    )
    if result.returncode != 0:
        stderr = (result.stderr or b"").decode("utf-8", errors="replace")
        pytest.fail(f"docker compose up failed (exit {result.returncode}):\n{stderr}")

    # Wait for the app container healthcheck to report healthy.
    _wait_for_health(start)


def _wait_for_health(start: float) -> None:
    """Poll ``docker inspect`` until the app container reports healthy."""
    app_container = f"{SMOKE_PROJECT}-app-1"
    deadline = _elapsed(start) + HEALTH_POLL_TIMEOUT

    while _elapsed(start) < deadline:
        try:
            result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.State.Health.Status}}",
                    app_container,
                ],
                capture_output=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                status = result.stdout.decode("utf-8").strip()
                if status == "healthy":
                    return
                # Still starting — keep polling
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        time.sleep(HEALTH_POLL_INTERVAL)

    pytest.fail(
        f"App container '{app_container}' did not become healthy "
        f"within {HEALTH_POLL_TIMEOUT}s"
    )


def _seed_database(start: float) -> str:
    """Substitute the marker in seed.sql and apply it to the db container.

    Returns the marker string.
    """
    _check_budget(start)

    marker = uuid.uuid4().hex

    seed_content = SEED_SQL.read_text(encoding="utf-8")
    seed_content = seed_content.replace("__MARKER__", marker)

    db_container = f"{SMOKE_PROJECT}-db-1"

    result = subprocess.run(
        ["docker", "exec", "-i", db_container, "psql", "-U", "postgres", "-d", "test"],
        input=seed_content.encode("utf-8"),
        capture_output=True,
        timeout=DOCKER_EXEC_TIMEOUT,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or b"").decode("utf-8", errors="replace")
        pytest.fail(f"Seed SQL failed (exit {result.returncode}):\n{stderr}")

    return marker


def _run_probe(start: float, marker: str) -> dict[str, Any]:
    """Run the in-network probe and return the parsed verdict.

    The probe container attaches to the ``probe`` network of the smoke stack.
    """
    _check_budget(start)

    probe_network = f"{SMOKE_PROJECT}_probe"

    probe_path_on_host = str(PROBE_SCRIPT.resolve())
    probe_path_in_container = "/probe.py"

    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            probe_network,
            "-v",
            f"{probe_path_on_host}:{probe_path_in_container}:ro",
            "-e",
            "APP_BASE_URL=http://app:8901",
            "-e",
            f"MARKER={marker}",
            "python:3.12-slim",
            "python",
            probe_path_in_container,
        ],
        capture_output=True,
        timeout=PROBE_TIMEOUT,
        check=False,
        cwd=str(WORKTREE_ROOT),
    )

    stdout_text = result.stdout.decode("utf-8", errors="replace").strip()
    stderr_text = result.stderr.decode("utf-8", errors="replace").strip()

    if not stdout_text:
        pytest.fail(f"Probe produced no stdout output.\nstderr: {stderr_text}")

    try:
        verdict: dict[str, Any] = json.loads(stdout_text)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"Probe stdout is not valid JSON: {exc}\nRaw stdout: {stdout_text!r}"
        )

    if result.returncode != 0:
        print(f"\n--- Probe verdict (stderr) ---\n{stderr_text}", flush=True)

    return verdict


def _teardown_stack() -> None:
    """Always tear down the smoke stack, regardless of test outcome."""
    compose_cmd = [
        "docker",
        "compose",
        "-p",
        SMOKE_PROJECT,
        "-f",
        str(COMPOSE_FILE),
        "down",
        "-v",
        "--remove-orphans",
    ]
    try:
        subprocess.run(
            compose_cmd,
            capture_output=True,
            timeout=60,
            check=False,
            cwd=str(WORKTREE_ROOT),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # Best-effort teardown — don't mask the original failure.
        pass


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------


def test_users_roundtrip_smoke() -> None:
    """Run the full users round-trip smoke oracle.

    Steps:
        1. Ensure ``apitest-app:smoke`` image exists.
        2. Deploy the sandboxed stack.
        3. Wait for app healthcheck.
        4. Seed the database with a per-run marker.
        5. Run the in-network probe.
        6. Assert on the probe verdict.
        7. Teardown unconditionally.
    """
    start = time.monotonic()

    # --- Docker availability check (fail loud, never skip) ---
    if not _docker_available():
        pytest.fail(
            "Docker is unreachable — the smoke oracle requires a running "
            "Docker daemon. This is a hard failure, not a skip."
        )

    try:
        # Step 1: Ensure image
        _ensure_image(start)

        # Step 2 & 3: Deploy and wait healthy
        _deploy_stack(start)

        # Step 4: Seed database
        marker = _seed_database(start)

        # Step 5: Run probe
        verdict = _run_probe(start, marker)

        # Step 6: Assert on verdict
        assert verdict.get("pass") is True, (
            f"Probe verdict failed. Full verdict:\n{json.dumps(verdict, indent=2)}"
        )
        checks = verdict.get("checks", [])
        for check in checks:
            assert check.get("pass") is True, (
                f"Check '{check.get('id')}' failed: {check.get('detail')}"
            )

    finally:
        # Step 7: Always teardown
        _teardown_stack()
