"""The in-memory SQLite address the harness falls back to, and what it must do.

WHY THESE TESTS EXIST. SQLAlchemy changed how it writes the in-memory SQLite
address: 2.0 writes ``sqlite+aiosqlite:///:memory:`` and 2.1 writes
``sqlite+aiosqlite:///%3Amemory%3A``. A harness that hard-codes either spelling
is wrong on one of them — the address it holds no longer matches the one the
engine reports, which is exactly what broke the harness's own tests under 2.1.

So these tests pin what the harness does about the change, not which spelling a
particular SQLAlchemy happens to use: the address is settled so that the engine
built from it says the same thing back, on any 2.x, and it must always name a
real in-memory database rather than a file that happens to be called
``%3Amemory%3A``. Nothing here depends on the database the run settled on, so
the tests read the same way against PostgreSQL as against SQLite.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from tests.conftest import (
    DEFAULT_TEST_DATABASE_URL,
    configured_database_url,
    database_engine_for_one_test,
)

# What the harness used to hard-code: the plain SQLite driver, no aiosqlite, and
# the in-memory name spelled raw. It must never come back.
LEGACY_UNENCODED_URL = "sqlite:///:memory:"

# The environment a run's database is read from. Both names are pinned in any
# test here that asks the harness what it was told, so its answer cannot depend
# on the machine the test happens to run on.
DATABASE_URL_ENV = "DATABASE_URL"
USE_SQLITE_ENV = "API_TEST_TESTS_USE_SQLITE"


def _no_address_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    """Say plainly that this run was given no database of its own.

    Args:
        monkeypatch: The pytest fixture that keeps the change to this test.
    """
    monkeypatch.delenv(DATABASE_URL_ENV, raising=False)
    monkeypatch.delenv(USE_SQLITE_ENV, raising=False)


class TestTheAddressIsSpelledTheWayThisSqlAlchemySpellsIt:
    """The fallback address matches what an engine built from it reports."""

    def test_it_is_already_in_the_form_the_installed_sqlalchemy_writes(
        self,
    ) -> None:
        """Reading the address and writing it back changes nothing.

        This is the round trip that broke: an engine built from a raw
        ``:memory:`` reports ``%3Amemory%3A`` under SQLAlchemy 2.1, so the
        address held by the harness and the address reported by the engine
        stopped agreeing. Whichever 2.x is installed, the stored address must
        already be the one that version writes.
        """
        assert str(make_url(DEFAULT_TEST_DATABASE_URL)) == DEFAULT_TEST_DATABASE_URL

    async def test_the_engine_built_from_it_reports_that_same_address(
        self,
    ) -> None:
        """The engine's own address is the harness's, character for character."""
        async with database_engine_for_one_test(None) as engine:
            assert str(engine.url) == DEFAULT_TEST_DATABASE_URL

    def test_it_is_not_the_legacy_unencoded_address(self) -> None:
        """The old ``sqlite:///:memory:`` address is gone for good."""
        assert DEFAULT_TEST_DATABASE_URL != LEGACY_UNENCODED_URL
        assert make_url(DEFAULT_TEST_DATABASE_URL).get_driver_name() == "aiosqlite"

    def test_it_names_the_in_memory_sqlite_database_of_old(self) -> None:
        """Whatever the spelling, it is SQLite in memory and nothing else."""
        url = make_url(DEFAULT_TEST_DATABASE_URL)
        assert url.get_backend_name() == "sqlite"
        assert url.host is None
        assert url.password is None


class TestTheAddressReallyOpensAnInMemoryDatabase:
    """The address must name memory, not a file whose name looks like memory."""

    async def test_the_database_it_opens_has_no_file_behind_it(self) -> None:
        """The engine holds its rows in memory, on every SQLAlchemy 2.x.

        SQLAlchemy 2.0 does not decode ``%3Amemory%3A``: an engine given that
        spelling opens a file by that name in the working directory and calls it
        a database. ``PRAGMA database_list`` says which of the two this is —
        an empty file name means memory.
        """
        async with database_engine_for_one_test(None) as engine:
            async with engine.connect() as conn:
                where = await conn.execute(text("PRAGMA database_list"))
                files = [row[2] for row in where]
                assert files, "SQLite listed no databases at all"
                assert set(files) == {""}, files

    async def test_the_tables_are_really_there_and_empty(self) -> None:
        """The harness's tables are made in it, as they always were."""
        async with database_engine_for_one_test(None) as engine:
            async with engine.connect() as conn:
                count = await conn.execute(text("SELECT COUNT(*) FROM users"))
                assert count.scalar() == 0


class TestNothingNamedMeansThisAddress:
    """With no address in the environment, this is what a developer gets."""

    async def test_the_default_engine_is_the_in_memory_sqlite(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No address named, so the fallback address is the one opened."""
        _no_address_is_named(monkeypatch)
        assert configured_database_url() is None

        async with database_engine_for_one_test(configured_database_url()) as engine:
            assert str(engine.url) == DEFAULT_TEST_DATABASE_URL
            async with engine.connect() as conn:
                count = await conn.execute(text("SELECT COUNT(*) FROM users"))
                assert count.scalar() == 0
