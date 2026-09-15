"""Tests for the GET /users/created-per-day endpoint and its count query.

The endpoint returns the number of users created on each of the last seven
days, oldest first, with the current day as the newest entry (ASSUM-001) and
exactly seven data points regardless of how sparse the data is (ASSUM-002).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from http import HTTPStatus
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import CreatedPerDayResponse, UserCreate

WINDOW_DAYS = 7


def expected_window() -> list[str]:
    """Return the ISO dates the endpoint must report, oldest first."""
    today = date.today()
    return [
        (today - timedelta(days=offset)).isoformat()
        for offset in range(WINDOW_DAYS - 1, -1, -1)
    ]


async def create_user_on(db: AsyncSession, email: str, when: datetime) -> None:
    """Create a user and backdate its creation timestamp to ``when``."""
    user = await crud.create_user(
        db,
        UserCreate(email=email, full_name=email.split("@")[0]),
    )
    user.created_at = when
    await db.flush()
    await db.refresh(user)


def midnight(day: date) -> datetime:
    """Return midnight at the start of ``day`` (matches the naive column)."""
    return datetime(day.year, day.month, day.day)


class TestCreatedPerDayEndpoint:
    """Behaviour of GET /users/created-per-day."""

    async def test_returns_200_with_seven_data_points(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-001: the endpoint answers 200 OK with exactly seven data points."""
        response = await async_client.get("/users/created-per-day")

        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == WINDOW_DAYS

    async def test_data_points_are_ordered_oldest_first(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-002: dates run oldest to newest, covering the seven-day window."""
        response = await async_client.get("/users/created-per-day")

        assert response.status_code == HTTPStatus.OK
        dates = [entry["date"] for entry in response.json()]
        assert dates == expected_window()
        assert dates == sorted(dates)

    async def test_newest_entry_is_today(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-002: the current day is the most recent date in the response."""
        response = await async_client.get("/users/created-per-day")

        assert response.json()[-1]["date"] == date.today().isoformat()

    async def test_no_date_older_than_the_window(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-002: nothing older than seven days ago is reported."""
        response = await async_client.get("/users/created-per-day")

        oldest_allowed = date.today() - timedelta(days=WINDOW_DAYS - 1)
        for entry in response.json():
            assert date.fromisoformat(entry["date"]) >= oldest_allowed

    async def test_each_data_point_has_date_and_count(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-002: every data point carries an ISO date and an integer count."""
        response = await async_client.get("/users/created-per-day")

        for entry in response.json():
            assert set(entry) == {"date", "count"}
            assert date.fromisoformat(entry["date"])
            assert isinstance(entry["count"], int)
            assert entry["count"] >= 0

    async def test_returns_zero_counts_when_no_users_created(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-001: with no creations the window is still seven zeroed days."""
        response = await async_client.get("/users/created-per-day")

        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert len(body) == WINDOW_DAYS
        assert all(entry["count"] == 0 for entry in body)

    async def test_zero_days_are_included_alongside_counted_days(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-002: days without creations appear with a count of zero."""
        today = date.today()
        await create_user_on(db_session, "today@example.com", midnight(today))
        await create_user_on(
            db_session,
            "older@example.com",
            midnight(today - timedelta(days=3)),
        )

        response = await async_client.get("/users/created-per-day")

        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert len(body) == WINDOW_DAYS
        by_date = {entry["date"]: entry["count"] for entry in body}
        assert by_date[today.isoformat()] == 1
        assert by_date[(today - timedelta(days=3)).isoformat()] == 1
        assert by_date[(today - timedelta(days=1)).isoformat()] == 0

    async def test_post_is_rejected(self, async_client: AsyncClient) -> None:
        """AC-001: the endpoint is read-only, so POST is not allowed."""
        response = await async_client.post("/users/created-per-day")

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    async def test_returns_503_when_db_unavailable(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """The endpoint degrades to 503 rather than a stack trace."""
        with patch.object(crud, "count_users_created_per_day") as mock_count:
            mock_count.side_effect = SQLAlchemyError("Database connection failed")

            response = await async_client.get("/users/created-per-day")

            assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
            assert "Database unavailable" in response.json()["detail"]


class TestCreatedPerDayCrud:
    """Behaviour of crud.count_users_created_per_day."""

    async def test_returns_seven_zeroed_days_for_empty_table(
        self, db_session: AsyncSession
    ) -> None:
        """An empty table still yields the full seven-day window."""
        rows = await crud.count_users_created_per_day(db_session)

        assert [row["date"] for row in rows] == expected_window()
        assert all(row["count"] == 0 for row in rows)

    async def test_counts_are_grouped_per_day(self, db_session: AsyncSession) -> None:
        """Two users on one day and one on another are counted separately."""
        today = date.today()
        for index in range(2):
            await create_user_on(
                db_session,
                f"today{index}@example.com",
                midnight(today).replace(hour=12),
            )
        await create_user_on(
            db_session,
            "yesterday@example.com",
            midnight(today - timedelta(days=1)),
        )

        rows = await crud.count_users_created_per_day(db_session)

        by_date = {row["date"]: row["count"] for row in rows}
        assert by_date[today.isoformat()] == 2
        assert by_date[(today - timedelta(days=1)).isoformat()] == 1

    async def test_users_outside_the_window_are_excluded(
        self, db_session: AsyncSession
    ) -> None:
        """Creations before the window (or in the future) are not counted."""
        today = date.today()
        await create_user_on(
            db_session,
            "stale@example.com",
            midnight(today - timedelta(days=WINDOW_DAYS)),
        )
        await create_user_on(
            db_session,
            "midnight-edge@example.com",
            midnight(today - timedelta(days=WINDOW_DAYS - 1)),
        )

        rows = await crud.count_users_created_per_day(db_session)

        by_date = {row["date"]: row["count"] for row in rows}
        assert by_date[(today - timedelta(days=WINDOW_DAYS - 1)).isoformat()] == 1
        assert sum(by_date.values()) == 1

    async def test_soft_deleted_users_are_excluded(
        self, db_session: AsyncSession
    ) -> None:
        """Soft-deleted users do not inflate a day's count."""
        today = date.today()
        await create_user_on(db_session, "kept@example.com", midnight(today))
        removed = await crud.create_user(
            db_session, UserCreate(email="removed@example.com")
        )
        removed.created_at = midnight(today)
        await db_session.flush()
        await crud.delete_user(db_session, str(removed.id))

        rows = await crud.count_users_created_per_day(db_session)

        by_date = {row["date"]: row["count"] for row in rows}
        assert by_date[today.isoformat()] == 1

    async def test_rejects_a_window_smaller_than_one_day(
        self, db_session: AsyncSession
    ) -> None:
        """A zero or negative window is a programming error, not an empty reply."""
        with pytest.raises(ValueError, match="at least 1"):
            await crud.count_users_created_per_day(db_session, days=0)


class TestCalendarDateCoercion:
    """The grouped day expression arrives differently per database driver."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (datetime(2026, 7, 9, 13, 45, 0), date(2026, 7, 9)),
            (date(2026, 7, 9), date(2026, 7, 9)),
            ("2026-07-09", date(2026, 7, 9)),
            ("2026-07-09 13:45:00", date(2026, 7, 9)),
        ],
    )
    def test_recognises_each_driver_shape(self, raw: object, expected: date) -> None:
        """datetime, date and ISO text all resolve to the same calendar day."""
        assert crud._as_calendar_date(raw) == expected

    @pytest.mark.parametrize("raw", ["not-a-date", None, 17])
    def test_rejects_values_that_are_not_dates(self, raw: object) -> None:
        """An unrecognisable day value is reported, never guessed as zero."""
        with pytest.raises(ValueError, match="Unexpected day value"):
            crud._as_calendar_date(raw)


class TestCreatedPerDaySchema:
    """Validation of the CreatedPerDayResponse schema."""

    def test_accepts_an_iso_calendar_date(self) -> None:
        """A well-formed day validates and keeps its ISO text."""
        entry = CreatedPerDayResponse(date="2026-07-09", count=3)

        assert entry.model_dump() == {"date": "2026-07-09", "count": 3}

    def test_rejects_a_malformed_date(self) -> None:
        """A malformed day is refused rather than silently passed through."""
        with pytest.raises(ValidationError, match="ISO-8601"):
            CreatedPerDayResponse(date="07/09/2026", count=1)

    def test_rejects_a_non_integer_count(self) -> None:
        """The count field must be an integer."""
        with pytest.raises(ValidationError):
            CreatedPerDayResponse(date="2026-07-09", count="many")
