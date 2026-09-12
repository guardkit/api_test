"""Give every pytest run the real database, not just the suite script's runs.

WHY THIS FILE EXISTS (2026-09-12). ``qa/run-suite.sh`` starts a throwaway
PostgreSQL and puts its address in DATABASE_URL, so the suite of record has a
real database. Nothing else did. The factory's build legs and the coach that
checks them run plain ``pytest`` with no such wrapper, so every build until now
was graded against in-memory SQLite — and SQLite forgives what PostgreSQL
refuses. That is how a feature reached the merge word with a shipped defect
behind it: ``count_users_today`` compares a timezone-aware datetime against a
column declared without one. SQLite shrugged; the live service answered 503.

So the tests now get the database themselves, rather than waiting to be handed
one. Anybody who runs ``pytest`` — the builder, the coach, the suite script, a
person at a terminal — runs against PostgreSQL, because the tests arrange it.

HOW. One long-lived container, named below, started the first time a run needs
it and reused by every run after: starting it costs a few seconds, reusing it
costs nothing. Each test still gets its own schema inside it (see
``tests/conftest.py``), so runs and tasks in parallel cannot see each other's
rows and reuse is safe.

WHERE IT RUNS. The build legs run inside this repository's Docker Sandbox,
which has its own Docker engine — the same engine that brings up this app's
compose stack, PostgreSQL included, on every deploy. So the container this file
asks for is one the sandbox already knows how to run.

WHAT IT NEVER DOES. It never falls back to SQLite in silence. If a real
database cannot be had, the run stops with a sentence saying why, because a
test that passes against the wrong database proves nothing — the whole lesson
of the day this file was written. Somebody who wants SQLite on purpose says so
with API_TEST_TESTS_USE_SQLITE=1 and gets a banner saying what they are
testing.

The password here is not a secret: it belongs to a throwaway local server that
holds nothing but test rows and listens on loopback only.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time

# The one container every run shares, and the image the app's own compose file
# already uses — so it is present wherever this app deploys.
CONTAINER_NAME = "api-test-suite-db"
IMAGE = "postgres:16-alpine"

# Throwaway credentials for a loopback-only server holding only test rows.
USER = "postgres"
PASSWORD = "test"
DATABASE = "test"

# The port asked for first. Docker picks a free one if this is taken, exactly as
# qa/run-suite.sh does, because a fixed port collided once with a container an
# earlier timed-out run had left behind.
PREFERRED_PORT = 55432

READY_TIMEOUT_SECONDS = 90
DOCKER_TIMEOUT_SECONDS = 120

# Say this to test against in-memory SQLite deliberately.
USE_SQLITE_ENV = "API_TEST_TESTS_USE_SQLITE"

# The address the tests read. Set here when nobody else set it.
DATABASE_URL_ENV = "DATABASE_URL"


class NoRealDatabase(Exception):
    """Raised when a real database cannot be had and the run must stop."""


def _docker(
    *args: str, timeout: int = DOCKER_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str]:
    """Run one docker command and hand back what it did.

    Args:
        *args: The docker arguments, without the word "docker".
        timeout: Seconds to wait before giving up on the command.

    Returns:
        subprocess.CompletedProcess[str]: The finished command.
    """
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _docker_is_usable() -> str | None:
    """Say why Docker cannot be used, or None when it can.

    Returns:
        str | None: A plain reason, or None when Docker answers.
    """
    if shutil.which("docker") is None:
        return "there is no docker command on the PATH"
    try:
        done = _docker("info", "--format", "{{.ServerVersion}}", timeout=30)
    except (OSError, subprocess.SubprocessError) as reason:
        return (
            f"the docker command could not be run ({type(reason).__name__}: {reason})"
        )
    if done.returncode != 0:
        detail = (done.stderr or done.stdout or "").strip().splitlines()
        first = detail[0] if detail else "no reason given"
        return f"the Docker engine did not answer: {first}"
    return None


def _published_port() -> int | None:
    """Return the loopback port the shared container publishes, if it is up.

    Returns:
        int | None: The port, or None when the container is not running.
    """
    done = _docker("port", CONTAINER_NAME, "5432/tcp", timeout=30)
    if done.returncode != 0:
        return None
    for line in done.stdout.splitlines():
        _, _, tail = line.strip().rpartition(":")
        if tail.isdigit():
            return int(tail)
    return None


def _container_state() -> str | None:
    """Return the shared container's state, or None when there is no such container.

    Returns:
        str | None: Docker's own word for the state ("running", "exited", ...).
    """
    done = _docker("inspect", "-f", "{{.State.Status}}", CONTAINER_NAME, timeout=30)
    if done.returncode != 0:
        return None
    return done.stdout.strip() or None


def _start_container() -> None:
    """Start the shared database container, making it if it is not there yet.

    Raises:
        NoRealDatabase: When Docker refuses to start it.
    """
    state = _container_state()
    if state == "running":
        return
    if state is not None:
        started = _docker("start", CONTAINER_NAME)
        if started.returncode == 0:
            return
        # A container left behind in a state it cannot leave is worth replacing
        # rather than arguing with: it holds nothing but dropped test schemas.
        _docker("rm", "-f", CONTAINER_NAME)

    made = _docker(
        "run",
        "-d",
        "--name",
        CONTAINER_NAME,
        "-e",
        f"POSTGRES_PASSWORD={PASSWORD}",
        "-e",
        f"POSTGRES_DB={DATABASE}",
        "-p",
        f"127.0.0.1:{PREFERRED_PORT}:5432",
        IMAGE,
    )
    if made.returncode == 0:
        return

    reason = (made.stderr or made.stdout or "").strip()
    # Two races are ordinary and neither is a failure: another run created the
    # container a moment ago, or something else holds the port we asked for.
    if "already in use by container" in reason or "Conflict" in reason:
        if _container_state() == "running" or _published_port() is not None:
            return
        _start_container_on_any_free_port()
        return
    if "port is already allocated" in reason or "address already in use" in reason:
        _start_container_on_any_free_port()
        return
    raise NoRealDatabase(
        f"Docker would not start the test database container: {reason}"
    )


def _start_container_on_any_free_port() -> None:
    """Start the shared container letting Docker choose the loopback port.

    Raises:
        NoRealDatabase: When Docker refuses this too.
    """
    _docker("rm", "-f", CONTAINER_NAME)
    made = _docker(
        "run",
        "-d",
        "--name",
        CONTAINER_NAME,
        "-e",
        f"POSTGRES_PASSWORD={PASSWORD}",
        "-e",
        f"POSTGRES_DB={DATABASE}",
        "-p",
        "127.0.0.1:0:5432",
        IMAGE,
    )
    if made.returncode != 0:
        reason = (made.stderr or made.stdout or "").strip()
        raise NoRealDatabase(
            f"Docker would not start the test database container: {reason}"
        )


def _wait_until_ready() -> None:
    """Wait for the database to start answering, or say it never did.

    Raises:
        NoRealDatabase: When the server is still not answering after the wait.
    """
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    last = "it never answered"
    while time.monotonic() < deadline:
        done = _docker("exec", CONTAINER_NAME, "pg_isready", "-U", USER, timeout=30)
        if done.returncode == 0:
            return
        last = (done.stdout or done.stderr or "").strip().splitlines()[-1:] or [
            "no reason given"
        ]
        last = last[0]
        time.sleep(1)
    raise NoRealDatabase(
        f"the test database did not come up within {READY_TIMEOUT_SECONDS} seconds "
        f"({last})"
    )


def address_of_the_shared_database() -> str:
    """Make sure the shared PostgreSQL is up and return its address.

    Returns:
        str: The SQLAlchemy address of the shared test database.

    Raises:
        NoRealDatabase: When no real database can be had, with the reason.
    """
    why_not = _docker_is_usable()
    if why_not is not None:
        raise NoRealDatabase(why_not)
    _start_container()
    _wait_until_ready()
    port = _published_port()
    if port is None:
        raise NoRealDatabase(
            "the test database container is running but publishes no port on "
            "loopback, so the tests cannot reach it"
        )
    return f"postgresql+asyncpg://{USER}:{PASSWORD}@127.0.0.1:{port}/{DATABASE}"


def settle_the_database_for_this_run() -> str:
    """Decide what this pytest run tests against, and say so in one line.

    Called once per pytest process, from ``pytest_configure``. When nobody has
    named a database, this starts (or reuses) the shared PostgreSQL and puts its
    address in the environment, so everything downstream — the fixtures, and any
    child process the run starts — sees it.

    Returns:
        str: One plain line naming what the run will test against.

    Raises:
        NoRealDatabase: When a real database was wanted and could not be had.
    """
    named = os.environ.get(DATABASE_URL_ENV, "").strip()
    if named:
        return "Tests run against the database named in DATABASE_URL."

    if os.environ.get(USE_SQLITE_ENV, "").strip() not in {"", "0", "false", "no"}:
        return (
            "Tests run against in-memory SQLite ON PURPOSE "
            f"({USE_SQLITE_ENV} is set). SQLite forgives things PostgreSQL "
            "refuses, so a pass here is not a pass against the real database."
        )

    try:
        address = address_of_the_shared_database()
    except NoRealDatabase as reason:
        raise NoRealDatabase(
            "These tests run against PostgreSQL, the database this app actually "
            f"uses, and one could not be started here: {reason}. The tests do "
            "not quietly fall back to SQLite, because a suite that passes "
            "against the wrong database proves nothing — that is exactly how a "
            "shipped defect reached production on 2026-09-12. Either start a "
            f"PostgreSQL and put its address in {DATABASE_URL_ENV}, or set "
            f"{USE_SQLITE_ENV}=1 to test against SQLite on purpose."
        ) from reason

    os.environ[DATABASE_URL_ENV] = address
    _, _, tail = address.rpartition("@")
    return f"Tests run against PostgreSQL in container {CONTAINER_NAME} at {tail}."
