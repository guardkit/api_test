"""Tests for ``GET /users/created-per-day``.

The endpoint's contract, in the words of the request it serves: the number of
users created on each of the last 7 days — today and the six days before it —
oldest first, counting soft-deleted users too. It takes no parameters and reads
the existing ``users.created_at`` column, so everything here is checked through
the running application: the ``async_client`` and ``override_get_db`` fixtures
in tests/conftest.py, and the ``seed_user`` fixture that stores a user at an
instant the test names.

The response *shape* — a JSON array of ``{date, count}`` objects — is pinned in
tests/users/test_analytics_schemas.py. What these tests pin is the three things
only the query and the route can get wrong: which seven days are in the window,
what order they come back in, and whether a soft-deleted user is counted.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date, datetime, time, timedelta
from http import HTTPStatus
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import analytics_crud, crud
from src.users.models import User

ENDPOINT = "/users/created-per-day"

# Today plus the six days before it.
WINDOW_DAYS = 7

# The seed_user fixture in tests/conftest.py: stores one user at an instant.
SeedUser = Callable[..., Awaitable[User]]

# One decoded entry of the response body.
Entry = dict[str, Any]


def _window_start(today: date) -> date:
    """The oldest day in the window, given what day it is."""
    return today - timedelta(days=WINDOW_DAYS - 1)


def _expected_dates(today: date) -> list[str]:
    """The window's days as ISO-8601 strings, oldest first."""
    start = _window_start(today)
    return [
        (start + timedelta(days=offset)).isoformat() for offset in range(WINDOW_DAYS)
    ]


def _midnight(day: date) -> datetime:
    """The first instant of a day."""
    return datetime.combine(day, time.min)


def _noon(day: date) -> datetime:
    """An instant well inside a day, clear of both midnight edges."""
    return datetime.combine(day, time(12, 0))


def _dates_of(entries: list[Entry]) -> list[str]:
    """The window's days as the response gave them, in the order it gave them."""
    return [str(entry["date"]) for entry in entries]


def _counts_of(entries: list[Entry]) -> list[int]:
    """The per-day counts, in the order the response gave the days."""
    return [int(entry["count"]) for entry in entries]


@pytest.fixture
def today() -> date:
    """The calendar day this test is judged against.

    The window is anchored on the clock of the process that answers the request,
    and these tests seed their rows against that same clock, so both sides of
    every comparison below read one machine's date.
    """
    return date.today()


class TestCreatedPerDayWindow:
    """AC-001: the window is today and the six days before it, and nothing else."""

    async def test_seven_entries_for_today_and_the_six_preceding_days(
        self, async_client: AsyncClient, override_get_db: None, today: date
    ) -> None:
        """Seven entries, one per day, ending with today."""
        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        entries = response.json()
        assert len(entries) == WINDOW_DAYS
        assert _dates_of(entries) == _expected_dates(today)
        assert _dates_of(entries)[-1] == today.isoformat()

    async def test_the_sixth_day_back_is_in_and_the_seventh_is_not(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        seed_user: SeedUser,
        today: date,
    ) -> None:
        """The window opens on the sixth day back and closes on today."""
        await seed_user("sixth-day@example.com", _noon(_window_start(today)))
        await seed_user(
            "seventh-day@example.com", _noon(today - timedelta(days=WINDOW_DAYS))
        )

        entries = (await async_client.get(ENDPOINT)).json()

        assert _dates_of(entries)[0] == _window_start(today).isoformat()
        day_before_window = (today - timedelta(days=WINDOW_DAYS)).isoformat()
        assert day_before_window not in _dates_of(entries)
        assert entries[0]["count"] == 1
        assert sum(_counts_of(entries)) == 1

    async def test_the_window_opens_and_closes_at_midnight(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        seed_user: SeedUser,
        today: date,
    ) -> None:
        """Each end of the window belongs to the day it is the first instant of.

        The first instant of the oldest day and the last instant of today are
        inside; the instant before the window opens and the first instant of
        tomorrow are outside.
        """
        first_day = _window_start(today)
        await seed_user("first-instant@example.com", _midnight(first_day))
        await seed_user(
            "last-instant@example.com",
            _midnight(today + timedelta(days=1)) - timedelta(microseconds=1),
        )
        await seed_user(
            "just-before@example.com", _midnight(first_day) - timedelta(microseconds=1)
        )
        await seed_user("tomorrow@example.com", _midnight(today + timedelta(days=1)))

        entries = (await async_client.get(ENDPOINT)).json()

        assert entries[0]["count"] == 1
        assert entries[-1]["count"] == 1
        assert sum(_counts_of(entries)) == 2

    async def test_a_user_created_tomorrow_is_not_counted(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        seed_user: SeedUser,
        today: date,
    ) -> None:
        """A row dated after today does not appear anywhere in the window."""
        await seed_user("future@example.com", _noon(today + timedelta(days=1)))

        entries = (await async_client.get(ENDPOINT)).json()

        assert _counts_of(entries) == [0] * WINDOW_DAYS


class TestCreatedPerDayOrdering:
    """AC-002: the entries run oldest to newest."""

    async def test_entries_run_oldest_to_newest_with_their_own_counts(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        seed_user: SeedUser,
        today: date,
    ) -> None:
        """Each day's count sits under that day's date, oldest day first.

        The days are seeded newest-first and the counts are not monotonic, so
        neither the insertion order nor a sorted-by-count accident can produce
        the expected answer.
        """
        expected_counts = [2, 1, 3, 1, 2, 0, 1]
        for offset in range(WINDOW_DAYS - 1, -1, -1):
            day = today - timedelta(days=offset)
            index = WINDOW_DAYS - 1 - offset
            for nth in range(expected_counts[index]):
                await seed_user(f"day{index}-user{nth}@example.com", _noon(day))

        entries = (await async_client.get(ENDPOINT)).json()

        assert _dates_of(entries) == _expected_dates(today)
        assert _counts_of(entries) == expected_counts

        days = [date.fromisoformat(entry) for entry in _dates_of(entries)]
        assert days == sorted(days)
        assert all(
            later - earlier == timedelta(days=1)
            for earlier, later in zip(days, days[1:], strict=False)
        )

    async def test_the_query_yields_one_row_per_day_oldest_first(
        self, db_session: AsyncSession, seed_user: SeedUser, today: date
    ) -> None:
        """The same window at the query layer, for where a failure actually is."""
        await seed_user("oldest@example.com", _noon(_window_start(today)))
        await seed_user("newest@example.com", _noon(today))

        rows = await analytics_crud.get_created_per_day(db_session)

        start = _window_start(today)
        assert [row["date"] for row in rows] == [
            start + timedelta(days=offset) for offset in range(WINDOW_DAYS)
        ]
        assert [row["count"] for row in rows] == [1, 0, 0, 0, 0, 0, 1]


class TestCreatedPerDayCountsSoftDeletedUsers:
    """AC-003: a soft-deleted user is still a user created that day."""

    async def test_a_soft_deleted_user_counts_on_the_day_they_were_created(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
        seed_user: SeedUser,
        today: date,
    ) -> None:
        """Today's count covers the deleted and the living alike."""
        deleted = await seed_user("deleted@example.com", _noon(today))
        await seed_user("living@example.com", _noon(today))
        assert await crud.delete_user(db_session, deleted.id) is True

        entries = (await async_client.get(ENDPOINT)).json()

        assert entries[-1]["count"] == 2
        # The live-only count is the difference this endpoint deliberately makes.
        assert await crud.count_users(db_session) == 1

    async def test_a_whole_window_of_soft_deleted_users_still_counts(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
        seed_user: SeedUser,
        today: date,
    ) -> None:
        """Two users on each of the seven days, every one of them deleted."""
        for offset in range(WINDOW_DAYS):
            day = today - timedelta(days=offset)
            for nth in range(2):
                await seed_user(f"d{offset}-u{nth}@example.com", _noon(day))

        doomed = (
            (await db_session.execute(select(User).order_by(User.email)))
            .scalars()
            .all()
        )
        for user in doomed:
            assert await crud.delete_user(db_session, user.id) is True

        entries = (await async_client.get(ENDPOINT)).json()

        assert _counts_of(entries) == [2] * WINDOW_DAYS
        assert await crud.count_users(db_session) == 0

    async def test_deleting_a_user_never_moves_or_empties_a_day(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
        seed_user: SeedUser,
        today: date,
    ) -> None:
        """Soft-deleting cannot move a count or empty a day."""
        doomed = [
            await seed_user(f"gone{nth}@example.com", _noon(today - timedelta(days=3)))
            for nth in range(3)
        ]

        before = (await async_client.get(ENDPOINT)).json()
        for user in doomed:
            assert await crud.delete_user(db_session, user.id) is True
        after = (await async_client.get(ENDPOINT)).json()

        assert _counts_of(before)[WINDOW_DAYS - 4] == 3
        assert after == before


class TestCreatedPerDaySurface:
    """The route's own surface: the path, and what one entry is made of."""

    async def test_an_empty_window_answers_seven_zero_entries(
        self, async_client: AsyncClient, override_get_db: None, today: date
    ) -> None:
        """Days with no users are present with a count of 0, not missing."""
        entries = (await async_client.get(ENDPOINT)).json()

        assert entries == [{"date": day, "count": 0} for day in _expected_dates(today)]

    async def test_the_literal_path_beats_the_user_id_route(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """``/users/created-per-day`` is its own route, not a malformed UUID.

        The users router declares ``GET /users/{user_id}``; had it been
        registered first, this request would have been answered 422.
        """
        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        assert isinstance(response.json(), list)

    async def test_each_entry_carries_exactly_a_date_and_a_count(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        seed_user: SeedUser,
        today: date,
    ) -> None:
        """Seven objects, each with an ISO date and an integer count."""
        await seed_user("shaped@example.com", _noon(today))

        entries = (await async_client.get(ENDPOINT)).json()

        assert len(entries) == WINDOW_DAYS
        for entry in entries:
            assert set(entry) == {"date", "count"}
            assert isinstance(entry["date"], str)
            date.fromisoformat(entry["date"])
            assert isinstance(entry["count"], int)
            assert not isinstance(entry["count"], bool)
