"""Tests for the GET /users/created-per-day endpoint and its CRUD helper.

Covers TASK-3560-001: a JSON array of date-count pairs for the last 7 days,
ordered oldest first, with zero counts for days that have no creations.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import UserCreate

ENDPOINT = "/users/created-per-day"
WINDOW_DAYS = 7


async def _create_user_on(db: AsyncSession, email: str, day: date) -> None:
    """Create a user whose creation timestamp falls at midday on ``day``.

    Args:
        db: The async database session.
        email: Unique email address for the user.
        day: The calendar day the user is backdated to.
    """
    user = await crud.create_user(db, UserCreate(email=email, full_name=email))
    user.created_at = datetime(day.year, day.month, day.day, 12, 0, 0)
    await db.flush()
    await db.refresh(user)


def _expected_days() -> list[date]:
    """Return the 7-day window, oldest day first (today-6 ... today)."""
    today = date.today()
    return [today - timedelta(days=back) for back in range(WINDOW_DAYS - 1, -1, -1)]


class TestCreatedPerDayEndpoint:
    """Tests for the GET /users/created-per-day endpoint contract."""

    # AC-001: the endpoint answers with a JSON array of date-count pairs.
    async def test_endpoint_returns_json_array_of_date_count_pairs(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Response is a JSON array whose items carry a date and a count."""
        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert isinstance(data, list)
        for item in data:
            assert isinstance(item, dict)
            assert set(item) == {"date", "count"}
            assert datetime.strptime(item["date"], "%Y-%m-%d")
            assert isinstance(item["count"], int)

    # AC-002: exactly 7 data points, oldest day first.
    async def test_endpoint_returns_exactly_seven_points_oldest_first(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Response holds exactly 7 entries covering today and the 6 days before."""
        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data) == WINDOW_DAYS

        days = [datetime.strptime(item["date"], "%Y-%m-%d").date() for item in data]
        assert days == _expected_days()
        assert days == sorted(days)
        assert days[-1] == date.today()
        assert days[0] == date.today() - timedelta(days=WINDOW_DAYS - 1)

    # AC-002: the window stays at 7 entries when more history exists.
    async def test_endpoint_ignores_days_older_than_the_window(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """History older than the window still yields 7 points, oldest 6 days back."""
        today = date.today()
        # One user on each of the 7 days before today: the oldest of those days
        # is 7 days back and falls outside the 7-day window.
        for back in range(1, 8):
            await _create_user_on(
                db_session, f"history-{back}@example.com", today - timedelta(days=back)
            )

        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data) == WINDOW_DAYS
        counts = {item["date"]: item["count"] for item in data}
        assert (today - timedelta(days=7)).isoformat() not in counts
        assert sum(counts.values()) == 6
        assert counts[(today - timedelta(days=6)).isoformat()] == 1
        assert counts[today.isoformat()] == 0

    # AC-003: empty history yields the full window with zero counts.
    async def test_endpoint_returns_zero_counts_for_empty_history(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """No users at all still produces 7 data points, all zero."""
        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data) == WINDOW_DAYS
        assert [item["count"] for item in data] == [0] * WINDOW_DAYS

    # AC-001/AC-002: counts are attributed to the day of creation.
    async def test_endpoint_counts_users_per_creation_day(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Each entry reports the users created on its own day."""
        today = date.today()
        for index in range(2):
            await _create_user_on(
                db_session, f"today-{index}@example.com", today - timedelta(days=6)
            )
        await _create_user_on(db_session, "mid@example.com", today - timedelta(days=2))

        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        counts = {item["date"]: item["count"] for item in response.json()}
        expected = {day.isoformat(): 0 for day in _expected_days()}
        expected[(today - timedelta(days=6)).isoformat()] = 2
        expected[(today - timedelta(days=2)).isoformat()] = 1
        assert counts == expected

    # Error handling: a database failure surfaces as 503, not a stack trace.
    async def test_endpoint_returns_503_when_the_database_fails(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """GET /users/created-per-day reports 503 when the query raises."""

        async def boom(*args: object, **kwargs: object) -> list[crud.DailyCount]:
            raise SQLAlchemyError("connection refused")

        monkeypatch.setattr(crud, "count_users_created_per_day", boom)

        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE

    # Spec: only GET is served; POST to the endpoint is rejected.
    async def test_post_to_endpoint_is_rejected(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """POST /users/created-per-day is not an accepted method."""
        response = await async_client.post(ENDPOINT)

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


class TestCreatedPerDayCrud:
    """Tests for the count_users_created_per_day CRUD helper in isolation."""

    # AC-002/AC-003: the helper always yields the full window.
    async def test_crud_returns_zero_filled_window_when_empty(
        self, db_session: AsyncSession
    ) -> None:
        """An empty table produces 7 ascending zero counts."""
        rows = await crud.count_users_created_per_day(db_session)

        assert [row.day for row in rows] == _expected_days()
        assert [row.count for row in rows] == [0] * WINDOW_DAYS

    # AC-001/AC-002: counts group by creation day.
    async def test_crud_groups_counts_by_creation_day(
        self, db_session: AsyncSession
    ) -> None:
        """Users are counted against the day their created_at falls on."""
        today = date.today()
        await _create_user_on(db_session, "a@example.com", today)
        await _create_user_on(db_session, "b@example.com", today)
        await _create_user_on(db_session, "c@example.com", today - timedelta(days=4))

        rows = await crud.count_users_created_per_day(db_session)

        # The window runs today-6 .. today, so 4 days back is entry index 2.
        assert [row.count for row in rows] == [0, 0, 1, 0, 0, 0, 2]

    # Counting convention: a soft-deleted user is no longer a standing creation.
    async def test_crud_excludes_soft_deleted_users(
        self, db_session: AsyncSession
    ) -> None:
        """A soft-deleted user no longer counts toward its creation day."""
        today = date.today()
        await _create_user_on(
            db_session, "doomed@example.com", today - timedelta(days=1)
        )

        rows = await crud.count_users_created_per_day(db_session)
        assert sum(row.count for row in rows) == 1

        user = await crud.get_user_by_email(db_session, "doomed@example.com")
        assert user is not None
        assert await crud.delete_user(db_session, str(user.id)) is True

        rows = await crud.count_users_created_per_day(db_session)
        assert sum(row.count for row in rows) == 0

    # Guard: the window must be a positive number of days.
    async def test_crud_rejects_a_non_positive_window(
        self, db_session: AsyncSession
    ) -> None:
        """A zero or negative window is a programming error, not an empty answer."""
        with pytest.raises(ValueError, match="days must be a positive"):
            await crud.count_users_created_per_day(db_session, days=0)
