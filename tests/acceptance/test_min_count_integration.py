"""Integration tests for the /users/count-by-domain endpoint min_count parameter.

Covers all acceptance criteria for the min_count query parameter:

  AC-001: Providing a valid min_count filters domains correctly
  AC-002: Omitting min_count returns all domains
  AC-003: A min_count of 0 includes all domains
  AC-004: A negative min_count returns a 400 Bad Request
  AC-005: A min_count exceeding 10,000 returns a 400 Bad Request
  AC-006: A non-integer min_count returns a 400 Bad Request
  AC-007: An empty min_count returns a 400 Bad Request
  AC-008: A very large min_count returns no domains

These tests use httpx AsyncClient with the application's test database
to verify the full request/response cycle over the wire.
"""

from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import UserCreate


class TestMinCountFiltering:
    """Integration tests for min_count query parameter filtering."""

    # ------------------------------------------------------------------
    # AC-001: Providing a valid min_count filters domains correctly
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ac001_valid_min_count_filters_domains(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """AC-001: Providing a valid min_count filters domains correctly.

        Invariant: Only domains with count >= min_count are returned.
        """
        # Seed users across multiple domains with varying counts.
        users_to_seed: list[tuple[str, str]] = [
            ("user1@example.com", "User 1"),
            ("user2@example.com", "User 2"),
            ("user3@example.com", "User 3"),
            ("user4@example.com", "User 4"),
            ("admin@other.org", "Admin"),
            ("dev@other.org", "Dev"),
            ("test@third.net", "Test"),
        ]
        for email, name in users_to_seed:
            await crud.create_user(
                db_session,
                UserCreate(email=email, full_name=name),
            )
        await db_session.commit()

        # Filter with min_count=2 should only return domains with >= 2 users.
        response = await async_client.get(
            "/users/count-by-domain", params={"min_count": 2}
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

        # Verify only qualifying domains are included.
        domains = {entry["domain"] for entry in data}
        assert domains == {"example.com", "other.org"}

        # Verify counts are correct.
        for entry in data:
            assert entry["count"] >= 2

        # Verify ordering: descending by count.
        counts = [entry["count"] for entry in data]
        assert counts == sorted(counts, reverse=True)

    # ------------------------------------------------------------------
    # AC-002: Omitting min_count returns all domains
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ac002_omit_min_count_returns_all_domains(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """AC-002: Omitting min_count returns all domains.

        Invariant: Without min_count, all domains with users are returned.
        """
        users_to_seed: list[tuple[str, str]] = [
            ("user1@example.com", "User 1"),
            ("admin@other.org", "Admin"),
            ("test@third.net", "Test"),
        ]
        for email, name in users_to_seed:
            await crud.create_user(
                db_session,
                UserCreate(email=email, full_name=name),
            )
        await db_session.commit()

        response = await async_client.get("/users/count-by-domain")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3

        domains = {entry["domain"] for entry in data}
        assert domains == {"example.com", "other.org", "third.net"}

    # ------------------------------------------------------------------
    # AC-003: min_count=0 includes all domains
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ac003_min_count_zero_includes_all(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """AC-003: A min_count of 0 includes all domains.

        Invariant: min_count=0 returns the same result as no filter.
        """
        users_to_seed: list[tuple[str, str]] = [
            ("user1@example.com", "User 1"),
            ("admin@other.org", "Admin"),
            ("test@third.net", "Test"),
        ]
        for email, name in users_to_seed:
            await crud.create_user(
                db_session,
                UserCreate(email=email, full_name=name),
            )
        await db_session.commit()

        response = await async_client.get(
            "/users/count-by-domain", params={"min_count": 0}
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3

        domains = {entry["domain"] for entry in data}
        assert domains == {"example.com", "other.org", "third.net"}

    # ------------------------------------------------------------------
    # AC-004: Negative min_count returns 400 Bad Request
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ac004_negative_min_count_returns_400(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-004: A negative min_count returns a 400 Bad Request.

        Invariant: Negative values are rejected with 400 status.
        """
        response = await async_client.get(
            "/users/count-by-domain", params={"min_count": "-1"}
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data
        assert "min_count must not be negative" in data["detail"]

    # ------------------------------------------------------------------
    # AC-005: min_count exceeding 10,000 returns 400 Bad Request
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ac005_min_count_exceeding_max_returns_400(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-005: A min_count exceeding 10,000 returns a 400 Bad Request.

        Invariant: Values above MIN_COUNT_MAX are rejected with 400 status.
        """
        response = await async_client.get(
            "/users/count-by-domain", params={"min_count": "10001"}
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data
        assert "min_count must not exceed 10000" in data["detail"]

    # ------------------------------------------------------------------
    # AC-006: Non-integer min_count returns 400 Bad Request
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ac006_non_integer_min_count_returns_400(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-006: A non-integer min_count returns a 400 Bad Request.

        Invariant: Non-numeric values are rejected with 400 status.
        """
        response = await async_client.get(
            "/users/count-by-domain", params={"min_count": "abc"}
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data
        assert "min_count must be a valid integer" in data["detail"]

    # ------------------------------------------------------------------
    # AC-007: Empty min_count returns 400 Bad Request
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ac007_empty_min_count_returns_400(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-007: An empty min_count returns a 400 Bad Request.

        Invariant: Empty string values are rejected with 400 status.
        """
        response = await async_client.get(
            "/users/count-by-domain", params={"min_count": ""}
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data
        assert "min_count must not be empty" in data["detail"]

    # ------------------------------------------------------------------
    # AC-008: Very large min_count returns no domains (empty list)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ac008_very_large_min_count_returns_empty(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """AC-008: A very large min_count returns no domains.

        Invariant: When min_count exceeds all domain counts, an empty list
        is returned with 200 status (not an error).
        """
        # Seed a few users.
        users_to_seed: list[tuple[str, str]] = [
            ("user1@example.com", "User 1"),
            ("user2@example.com", "User 2"),
            ("admin@other.org", "Admin"),
        ]
        for email, name in users_to_seed:
            await crud.create_user(
                db_session,
                UserCreate(email=email, full_name=name),
            )
        await db_session.commit()

        # Use a valid min_count within range but larger than any domain count.
        # 999999 exceeds MIN_COUNT_MAX (10,000) and would return 400, so we use
        # 1000 which is valid but exceeds all seeded domain counts (max=2).
        response = await async_client.get(
            "/users/count-by-domain", params={"min_count": "1000"}
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
