"""Tests for the GET /stats/users-created-per-day endpoint.

Covers:
- AC-001: Endpoint returns 200 OK
- AC-002: Response format matches specification (7 data points, date+count,
  ordered oldest first, zero-count days included)
- AC-003: POST method is rejected
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dependencies import get_db as app_get_db
from src.main import app
from src.stats.users_created import UsersCreatedPerDay

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _insert_user(db: AsyncSession, created_at: datetime) -> None:
    """Insert a raw user row with a specific created_at timestamp.

    Args:
        db: The async database session.
        created_at: The timestamp to set for the user (timezone-aware or naive).
    """
    user_id = (
        f"user-{created_at.strftime('%Y%m%d%H%M%S')}"
        f"-{abs(hash(str(created_at))) % 10000:04d}"
    )
    # Strip timezone info for the naive DateTime column
    naive_dt = created_at.replace(tzinfo=None) if created_at.tzinfo else created_at
    await db.execute(
        text(
            "INSERT INTO users (id, email, domain, full_name, is_active, "
            "created_at, updated_at) "
            "VALUES (:uid, :email, :domain, :name, :active, :created, :updated)"
        ),
        {
            "uid": user_id,
            "email": f"user_{user_id}@example.com",
            "domain": "example.com",
            "name": "Test User",
            "active": True,
            "created": naive_dt,
            "updated": naive_dt,
        },
    )
    await db.commit()


# ---------------------------------------------------------------------------
# AC-001: GET /stats/users-created-per-day returns 200 OK
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_endpoint_returns_200(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """AC-001: GET /stats/users-created-per-day returns HTTP 200."""
    response = await async_client.get("/stats/users-created-per-day")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_endpoint_content_type(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """AC-001: Response has application/json content type."""
    response = await async_client.get("/stats/users-created-per-day")

    assert "application/json" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# AC-002: Response format matches specification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_response_has_exactly_seven_entries(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """AC-002: Response contains exactly 7 data points."""
    response = await async_client.get("/stats/users-created-per-day")
    data = response.json()

    assert len(data) == 7


@pytest.mark.asyncio
async def test_response_entries_have_date_and_count(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """AC-002: Each entry has 'date' (str) and 'count' (int) fields."""
    response = await async_client.get("/stats/users-created-per-day")
    data = response.json()

    for entry in data:
        assert "date" in entry
        assert "count" in entry
        assert isinstance(entry["date"], str)
        assert isinstance(entry["count"], int)


@pytest.mark.asyncio
async def test_response_ordered_oldest_first(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """AC-002: Data points are ordered from oldest to newest."""
    response = await async_client.get("/stats/users-created-per-day")
    data = response.json()

    dates = [entry["date"] for entry in data]
    assert dates == sorted(dates)


@pytest.mark.asyncio
async def test_oldest_day_is_six_days_ago(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """AC-002: The oldest day in the response is exactly 6 days before today."""
    response = await async_client.get("/stats/users-created-per-day")
    data = response.json()

    oldest_date = date.fromisoformat(data[0]["date"])
    expected_oldest = date.today() - timedelta(days=6)
    assert oldest_date == expected_oldest


@pytest.mark.asyncio
async def test_newest_day_is_today(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """AC-002: The newest day in the response is today."""
    response = await async_client.get("/stats/users-created-per-day")
    data = response.json()

    newest_date = date.fromisoformat(data[-1]["date"])
    assert newest_date == date.today()


@pytest.mark.asyncio
async def test_empty_database_returns_zeros(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """AC-002: Empty database returns all zero counts."""
    response = await async_client.get("/stats/users-created-per-day")
    data = response.json()

    for entry in data:
        assert entry["count"] == 0


@pytest.mark.asyncio
async def test_zero_count_days_included(db_session: AsyncSession) -> None:
    """AC-002: Days with no users are reported with count 0.

    Inserts users on only 2 of the 7 days and verifies the other 5 days
    have count 0.
    """
    from httpx import ASGITransport

    today = date.today()
    # Insert users on day 2 and day 5 (relative to today)
    await _insert_user(
        db_session,
        datetime(today.year, today.month, today.day - 2, 10, 0, 0, tzinfo=UTC),
    )
    await _insert_user(
        db_session,
        datetime(today.year, today.month, today.day - 5, 14, 0, 0, tzinfo=UTC),
    )
    await db_session.commit()

    # Override get_db on the app to use this test session
    async def test_get_db():
        yield db_session

    app.dependency_overrides[app_get_db] = test_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/stats/users-created-per-day")
            data = response.json()

        # Verify we still get 7 entries
        assert len(data) == 7

        # The days with users should have count >= 1, others should be 0
        for entry in data:
            entry_date = date.fromisoformat(entry["date"])
            days_ago = (today - entry_date).days
            if days_ago == 2 or days_ago == 5:
                assert entry["count"] >= 1
            else:
                assert entry["count"] == 0
    finally:
        if app_get_db in app.dependency_overrides:
            del app.dependency_overrides[app_get_db]


@pytest.mark.asyncio
async def test_schema_validation() -> None:
    """AC-002: UsersCreatedPerDay schema validates correctly."""
    entry = UsersCreatedPerDay(date="2024-01-01", count=5)
    assert entry.date == "2024-01-01"
    assert entry.count == 5

    # Should reject invalid types
    with pytest.raises(ValueError):
        UsersCreatedPerDay(date=123, count=5)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AC-003: POST method is rejected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_rejected(async_client: AsyncClient, override_get_db: None) -> None:
    """AC-003: POST request to the endpoint is rejected."""
    response = await async_client.post("/stats/users-created-per-day")

    assert response.status_code == 405  # Method Not Allowed


# ---------------------------------------------------------------------------
# Integration test with real database session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_integration_with_db(db_session: AsyncSession) -> None:
    """Integration: endpoint returns correct counts from the database.

    Inserts users on specific dates and verifies the counts match.
    """
    from httpx import ASGITransport

    today = date.today()

    # Insert 3 users on day 3 ago, 1 user on day 1 ago
    for i in range(3):
        await _insert_user(
            db_session,
            datetime(today.year, today.month, today.day - 3, 10 + i, 0, 0, tzinfo=UTC),
        )
    await _insert_user(
        db_session,
        datetime(today.year, today.month, today.day - 1, 15, 0, 0, tzinfo=UTC),
    )
    await db_session.commit()

    # Override get_db on the app to use this test session
    async def test_get_db():
        yield db_session

    app.dependency_overrides[app_get_db] = test_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/stats/users-created-per-day")
            data = response.json()

        assert len(data) == 7

        # Find the entries for day 3 and day 1
        day3_count = None
        day1_count = None
        for entry in data:
            entry_date = date.fromisoformat(entry["date"])
            days_ago = (today - entry_date).days
            if days_ago == 3:
                day3_count = entry["count"]
            elif days_ago == 1:
                day1_count = entry["count"]

        assert day3_count == 3
        assert day1_count == 1
    finally:
        if app_get_db in app.dependency_overrides:
            del app.dependency_overrides[app_get_db]
