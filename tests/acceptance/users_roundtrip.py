"""Users round-trip oracle for the runtime smoke test.

Orchestrates the full smoke lifecycle:
  1. Build ``apitest-app:smoke`` from this worktree's root, on every run, and
     read the image id the build produced.
  2. Deploy the sandboxed stack via docker-compose.
  3. Prove the running ``app`` container uses that image id (loud failure
     naming both ids if not).
  4. Wait for the app container healthcheck to report healthy.
  5. Seed Postgres with a per-run ``uuid4().hex`` marker.
  6. Run the in-network probe (``qa/smoke/probe.py``) and assert on its verdict.
  7. Teardown unconditionally in a ``finally`` block.

The module never references ``apitest-f2``, ``apitest-f2-cand``, or host port
5433.  Docker-unreachable is a loud FAILURE (never a skip).

Why the image is built on every run (2026-09-06)
------------------------------------------------
Until 2026-09-06 this oracle built ``apitest-app:smoke`` only when the tag was
missing, so every run after 2026-07-25 tested the image built that day rather
than the code in the worktree it was asked about. On 2026-09-06 build
FEAT-8388 changed the users model (a ``domain`` column) without adding a
migration; this oracle ran and passed against the July image, and the deploy
into the sandbox then found the users table had no ``domain`` column on a
fresh database. Now the image is rebuilt from the worktree root on every run
(Docker's layer cache keeps a no-change rebuild to seconds; the 120-second
build budget stays), and after ``compose up`` the oracle reads the running
app container's image id and fails loudly, naming both ids, if it is not the
id the build produced. The schema in the stack comes from ``alembic upgrade
head`` in the image's entrypoint, never from ``create_all``.
``tests/test_roundtrip_oracle_builds_every_run.py`` pins all three.

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
IMAGE_TAG = "apitest-app:smoke"
APP_SERVICE = "app"
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


def _ensure_image(start: float) -> str:
    """Build ``apitest-app:smoke`` from the worktree root and return its image id.

    Built on every run since 2026-09-06 (see the module docstring): a present
    tag is not a reason to skip the build, because the tag says nothing about
    which code it was built from. Docker's layer cache keeps a no-change
    rebuild to seconds, within the same 120-second budget. The id returned is
    what ``docker image inspect`` reports right after the build;
    ``_deploy_stack`` checks the running container against it.
    """
    _check_budget(start)

    result = subprocess.run(
        ["docker", "build", "-t", IMAGE_TAG, "."],
        capture_output=True,
        timeout=IMAGE_BUILD_TIMEOUT,
        check=False,
        cwd=str(WORKTREE_ROOT),
    )
    if result.returncode != 0:
        stderr = (result.stderr or b"").decode("utf-8", errors="replace")
        pytest.fail(f"docker build failed (exit {result.returncode}):\n{stderr}")

    inspect = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE_TAG],
        capture_output=True,
        timeout=15,
        check=False,
    )
    if inspect.returncode != 0:
        stderr = (inspect.stderr or b"").decode("utf-8", errors="replace")
        pytest.fail(
            f"docker image inspect of {IMAGE_TAG} failed right after the build "
            f"(exit {inspect.returncode}):\n{stderr}"
        )
    image_id = (inspect.stdout or b"").decode("utf-8", errors="replace").strip()
    if not image_id:
        pytest.fail(
            f"docker image inspect returned no image id for {IMAGE_TAG} right "
            "after the build"
        )
    print(
        f"\n[oracle] built {IMAGE_TAG} from {WORKTREE_ROOT}: image id {image_id}",
        flush=True,
    )
    return image_id


def _running_app_image_id() -> str:
    """Return the image id of the smoke stack's ``app`` container.

    ``ps -q -a`` so the container is found even when it has already exited
    (a failed migration, say); the health wait reports that case on its own.
    """
    ps = subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            SMOKE_PROJECT,
            "-f",
            str(COMPOSE_FILE),
            "ps",
            "-q",
            "-a",
            APP_SERVICE,
        ],
        capture_output=True,
        timeout=15,
        check=False,
        cwd=str(WORKTREE_ROOT),
    )
    if ps.returncode != 0:
        stderr = (ps.stderr or b"").decode("utf-8", errors="replace")
        pytest.fail(
            f"docker compose ps for service '{APP_SERVICE}' in project "
            f"'{SMOKE_PROJECT}' failed (exit {ps.returncode}):\n{stderr}"
        )
    container_ids = [
        line.strip()
        for line in (ps.stdout or b"").decode("utf-8", errors="replace").splitlines()
        if line.strip()
    ]
    if len(container_ids) != 1:
        pytest.fail(
            f"Expected exactly one '{APP_SERVICE}' container in project "
            f"'{SMOKE_PROJECT}' after compose up, found {len(container_ids)}: "
            f"{container_ids}"
        )

    inspect = subprocess.run(
        ["docker", "inspect", "--format", "{{.Image}}", container_ids[0]],
        capture_output=True,
        timeout=15,
        check=False,
    )
    if inspect.returncode != 0:
        stderr = (inspect.stderr or b"").decode("utf-8", errors="replace")
        pytest.fail(
            f"docker inspect of the '{APP_SERVICE}' container {container_ids[0]} "
            f"failed (exit {inspect.returncode}):\n{stderr}"
        )
    image_id = (inspect.stdout or b"").decode("utf-8", errors="replace").strip()
    if not image_id:
        pytest.fail(
            f"docker inspect returned no image id for the '{APP_SERVICE}' "
            f"container {container_ids[0]}"
        )
    return image_id


def _prove_running_image(built_image_id: str) -> None:
    """Fail loudly unless the running ``app`` container uses the image just built.

    This is the proof that the oracle tests the code it was asked about
    (2026-09-06): the compose file names the tag, and the tag was just
    rebuilt, but only the running container's image id says which image the
    probe is really hitting.
    """
    running_image_id = _running_app_image_id()
    if running_image_id != built_image_id:
        pytest.fail(
            f"The smoke stack's '{APP_SERVICE}' container is not running the "
            f"image this run built, so the oracle would test some other image "
            f"than this worktree's code.\n"
            f"  built {IMAGE_TAG} image id:      {built_image_id}\n"
            f"  running app container image id: {running_image_id}"
        )
    print(
        f"[oracle] image proof: built {IMAGE_TAG} = {built_image_id}; "
        f"running {APP_SERVICE} container = {running_image_id}; match",
        flush=True,
    )


def _deploy_stack(start: float, built_image_id: str) -> None:
    """Bring up the smoke stack, prove it runs *built_image_id*, wait for health.

    The proof comes before the health wait so a wrong image fails at once
    rather than after a slow health timeout.
    """
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

    # Prove the container that came up is the image this run built.
    _prove_running_image(built_image_id)

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
        1. Build ``apitest-app:smoke`` from this worktree (every run).
        2. Deploy the sandboxed stack and prove it runs the image just built.
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
        # Step 1: Build the image from this worktree; keep the id it produced
        built_image_id = _ensure_image(start)

        # Step 2 & 3: Deploy, prove the running image, wait healthy
        _deploy_stack(start, built_image_id)

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
