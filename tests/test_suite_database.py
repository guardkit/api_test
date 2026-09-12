"""Tests for the code that gives every pytest run a real database.

None of these tests start a container or talk to Docker: every Docker command
is stood in for, so this file is safe to run anywhere, including on a machine
with no Docker at all.
"""

from __future__ import annotations

import subprocess

import pytest

from tests import suite_database


def _finished(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    """Build a stand-in for a finished docker command.

    Args:
        returncode: The exit code to report.
        stdout: What the command printed.
        stderr: What the command printed to its error stream.

    Returns:
        subprocess.CompletedProcess[str]: The stand-in.
    """
    return subprocess.CompletedProcess(
        args=["docker"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class TestWhatTheRunTestsAgainst:
    """The decision about which database a pytest run uses."""

    def test_an_address_already_given_is_left_alone(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A DATABASE_URL somebody else set is used as it stands."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:1/db")

        def never_called(*_args: str, **_kwargs: object) -> None:
            raise AssertionError("Docker must not be touched when an address was given")

        monkeypatch.setattr(suite_database, "_docker", never_called)

        line = suite_database.settle_the_database_for_this_run()

        assert "DATABASE_URL" in line

    def test_sqlite_on_purpose_says_so_loudly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Asking for SQLite is allowed, and the run says what it is testing."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv(suite_database.USE_SQLITE_ENV, "1")

        line = suite_database.settle_the_database_for_this_run()

        assert "SQLite" in line
        assert "PostgreSQL" in line
        assert "DATABASE_URL" not in __import__("os").environ

    def test_a_started_database_is_put_in_the_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the container comes up, its address becomes DATABASE_URL."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv(suite_database.USE_SQLITE_ENV, raising=False)
        monkeypatch.setattr(
            suite_database,
            "address_of_the_shared_database",
            lambda: "postgresql+asyncpg://postgres:test@127.0.0.1:55432/test",
        )

        line = suite_database.settle_the_database_for_this_run()

        import os

        assert os.environ["DATABASE_URL"] == (
            "postgresql+asyncpg://postgres:test@127.0.0.1:55432/test"
        )
        assert "PostgreSQL" in line
        assert "test" in line
        # The line names where it is, and never the password.
        assert "postgres:test@" not in line

    def test_no_database_stops_the_run_rather_than_using_sqlite(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A run that cannot get PostgreSQL stops, and says how to proceed."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv(suite_database.USE_SQLITE_ENV, raising=False)

        def refuse() -> str:
            raise suite_database.NoRealDatabase(
                "there is no docker command on the PATH"
            )

        monkeypatch.setattr(suite_database, "address_of_the_shared_database", refuse)

        with pytest.raises(suite_database.NoRealDatabase) as refusal:
            suite_database.settle_the_database_for_this_run()

        said = str(refusal.value)
        assert "no docker command" in said
        assert "do not quietly fall back" in said
        assert suite_database.USE_SQLITE_ENV in said
        assert "DATABASE_URL" in said


class TestFindingAndStartingTheContainer:
    """The Docker steps, with Docker stood in for."""

    def test_a_missing_docker_command_is_named_plainly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No docker on the PATH is reported as exactly that."""
        monkeypatch.setattr(suite_database.shutil, "which", lambda _name: None)

        assert (
            suite_database._docker_is_usable()
            == "there is no docker command on the PATH"
        )

    def test_an_engine_that_will_not_answer_is_named_plainly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A dead engine is reported with the reason Docker gave."""
        monkeypatch.setattr(
            suite_database.shutil, "which", lambda _name: "/usr/bin/docker"
        )
        monkeypatch.setattr(
            suite_database,
            "_docker",
            lambda *_a, **_k: _finished(
                1, stderr="Cannot connect to the Docker daemon"
            ),
        )

        why = suite_database._docker_is_usable()

        assert why is not None
        assert "Cannot connect to the Docker daemon" in why

    def test_the_published_port_is_read_from_docker(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The loopback port the container publishes is the one used."""
        monkeypatch.setattr(
            suite_database,
            "_docker",
            lambda *_a, **_k: _finished(0, stdout="5432/tcp -> 127.0.0.1:55432\n"),
        )

        assert suite_database._published_port() == 55432

    def test_no_container_means_no_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When there is no such container, no port is reported."""
        monkeypatch.setattr(suite_database, "_docker", lambda *_a, **_k: _finished(1))

        assert suite_database._published_port() is None

    def test_a_running_container_is_reused_not_restarted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A container that is already up is left exactly as it is."""
        calls: list[tuple[str, ...]] = []

        def record(*args: str, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            if args[0] == "inspect":
                return _finished(0, stdout="running\n")
            raise AssertionError(f"a running container must not be touched: {args}")

        monkeypatch.setattr(suite_database, "_docker", record)

        suite_database._start_container()

        assert [c[0] for c in calls] == ["inspect"]

    def test_a_stopped_container_is_started_again(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A container left behind by an earlier run is started, not replaced."""
        calls: list[str] = []

        def record(*args: str, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(args[0])
            if args[0] == "inspect":
                return _finished(0, stdout="exited\n")
            if args[0] == "start":
                return _finished(0)
            raise AssertionError(f"unexpected docker call: {args}")

        monkeypatch.setattr(suite_database, "_docker", record)

        suite_database._start_container()

        assert calls == ["inspect", "start"]

    def test_a_taken_port_is_not_a_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the preferred port is taken, Docker is asked to choose one."""
        calls: list[str] = []

        def record(*args: str, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(args[0])
            if args[0] == "inspect":
                return _finished(1)
            if (
                args[0] == "run"
                and "-p" in args
                and f"127.0.0.1:{suite_database.PREFERRED_PORT}:5432" in args
            ):
                return _finished(
                    1,
                    stderr="Bind for 127.0.0.1:55432 failed: port is already allocated",
                )
            if args[0] == "rm":
                return _finished(0)
            if args[0] == "run":
                return _finished(0)
            raise AssertionError(f"unexpected docker call: {args}")

        monkeypatch.setattr(suite_database, "_docker", record)

        suite_database._start_container()

        assert calls.count("run") == 2

    def test_a_refusal_docker_cannot_explain_is_raised(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unexpected Docker refusal stops the run with Docker's own words."""

        def record(*args: str, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            if args[0] == "inspect":
                return _finished(1)
            return _finished(1, stderr="no space left on device")

        monkeypatch.setattr(suite_database, "_docker", record)

        with pytest.raises(
            suite_database.NoRealDatabase, match="no space left on device"
        ):
            suite_database._start_container()

    def test_a_database_that_never_answers_stops_the_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Waiting for a database that never comes up ends in a plain refusal."""
        monkeypatch.setattr(suite_database, "READY_TIMEOUT_SECONDS", 0.05)
        monkeypatch.setattr(
            suite_database,
            "_docker",
            lambda *_a, **_k: _finished(1, stdout="no response"),
        )
        monkeypatch.setattr(suite_database.time, "sleep", lambda _s: None)

        with pytest.raises(suite_database.NoRealDatabase, match="did not come up"):
            suite_database._wait_until_ready()
