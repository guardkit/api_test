"""Tests for the harness's own choice of database.

The suite of record (qa/run-suite.sh) starts a real PostgreSQL and puts its
address in DATABASE_URL. These tests prove the harness honours that address,
still behaves exactly as it always did when nothing is set, and fails loudly
rather than quietly testing against SQLite when the named server is missing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from tests.conftest import (
    DEFAULT_TEST_DATABASE_URL,
    configured_database_url,
    database_engine_for_one_test,
)

# A port nothing listens on, used to prove the harness refuses to guess.
UNREACHABLE_URL = "postgresql+asyncpg://postgres:test@127.0.0.1:1/test"


class TestTheAddressTheHarnessUses:
    """Which database the harness opens, and when."""

    def test_no_address_set_means_no_address(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With DATABASE_URL unset or empty, the harness is told nothing."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        assert configured_database_url() is None

        monkeypatch.setenv("DATABASE_URL", "   ")
        assert configured_database_url() is None

    def test_an_address_that_is_set_is_read_as_written(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With DATABASE_URL set, the harness reads exactly that address."""
        monkeypatch.setenv("DATABASE_URL", UNREACHABLE_URL)
        assert configured_database_url() == UNREACHABLE_URL

    async def test_nothing_set_gives_the_in_memory_sqlite_it_always_gave(
        self,
    ) -> None:
        """With no address, the engine is the in-memory SQLite of old."""
        async with database_engine_for_one_test(None) as engine:
            assert str(engine.url) == DEFAULT_TEST_DATABASE_URL
            async with engine.connect() as conn:
                count = await conn.execute(text("SELECT COUNT(*) FROM users"))
                assert count.scalar() == 0

    async def test_an_address_that_is_set_is_the_engine_that_is_opened(
        self, tmp_path: Path
    ) -> None:
        """The engine points at the address given, not at the default."""
        given = f"sqlite+aiosqlite:///{tmp_path}/given.db"
        async with database_engine_for_one_test(given) as engine:
            assert str(engine.url) == given
            assert str(engine.url) != DEFAULT_TEST_DATABASE_URL

    async def test_the_fixture_uses_the_address_the_suite_set(
        self, db_engine: AsyncEngine
    ) -> None:
        """The fixture every test uses follows the same rule.

        Run with the suite's PostgreSQL, this proves the tests really are
        running against that server. Run with nothing set, it proves today's
        in-memory SQLite is still what a developer gets.
        """
        asked_for = configured_database_url()
        if asked_for is None:
            assert str(db_engine.url) == DEFAULT_TEST_DATABASE_URL
            return

        wanted = make_url(asked_for)
        assert db_engine.url.host == wanted.host
        assert db_engine.url.port == wanted.port
        assert db_engine.url.database == wanted.database

    async def test_each_test_is_kept_apart_from_every_other_test(
        self, db_engine: AsyncEngine
    ) -> None:
        """Isolation holds in both modes, by different means.

        In-memory SQLite is private to the test by its nature. A shared
        PostgreSQL is not, so the test runs in a schema of its own.
        """
        if db_engine.url.get_backend_name() == "sqlite":
            assert db_engine.url.database in (None, ":memory:")
            return

        async with db_engine.connect() as conn:
            where = await conn.execute(text("SELECT current_schema()"))
            schema = where.scalar()
        assert schema is not None
        assert schema != "public"
        assert schema.startswith("test_")


class TestAMissingServerStopsTheRun:
    """A named server that is not there must never be silently replaced."""

    async def test_it_fails_with_a_plain_sentence_and_does_not_fall_back(
        self,
    ) -> None:
        """The failure names the host and the port and hides the password."""
        with pytest.raises(pytest.fail.Exception) as stopped:
            async with database_engine_for_one_test(UNREACHABLE_URL):
                raise AssertionError(
                    "the harness opened an engine on a server that is not there"
                )

        said = str(stopped.value)
        assert "host 127.0.0.1" in said
        assert "port 1" in said
        assert "could not be reached" in said
        assert "do not fall back" in said
        assert ":test@" not in said
        assert "***" in said


class TestTheHarnessLeavesNothingBehind:
    """Whatever database is used, a test cleans up after itself."""

    async def test_the_tables_or_the_schema_are_gone_afterwards(
        self, tmp_path: Path
    ) -> None:
        """After the engine closes, nothing it made is still there."""
        asked_for = configured_database_url()
        if asked_for is None or make_url(asked_for).get_backend_name() == "sqlite":
            given = f"sqlite+aiosqlite:///{tmp_path}/leftovers.db"
            async with database_engine_for_one_test(given):
                pass
            after = create_async_engine(given)
            try:
                async with after.connect() as conn:
                    tables = await conn.execute(
                        text("SELECT name FROM sqlite_master WHERE type='table'")
                    )
                    assert tables.scalars().all() == []
            finally:
                await after.dispose()
            return

        async with database_engine_for_one_test(asked_for) as engine:
            async with engine.connect() as conn:
                where = await conn.execute(text("SELECT current_schema()"))
                schema = where.scalar()

        after = create_async_engine(asked_for)
        try:
            async with after.connect() as conn:
                still_there = await conn.execute(
                    text(
                        "SELECT schema_name FROM information_schema.schemata "
                        "WHERE schema_name = :name"
                    ),
                    {"name": schema},
                )
                assert still_there.scalars().all() == []
        finally:
            await after.dispose()
