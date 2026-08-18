"""Acceptance tests for the /recent-users endpoint.

Covers all 9 scenarios from the feature specification:

  SC-01: Requesting recent users without a limit returns the default number
         of newest users
  SC-02: Requesting recent users with a valid explicit limit returns that
         many newest users
  SC-03: Requesting recent users at the maximum allowed limit returns that
         many users
  SC-04: Requesting recent users with a limit exceeding the maximum is
         rejected
  SC-05: Requesting recent users with a limit of 1 returns a single newest
         user
  SC-06: Requesting recent users with a limit of zero is rejected
  SC-07: Requesting recent users with a negative limit is rejected
  SC-08: Requesting recent users with a non-integer limit is rejected
  SC-09: Requesting recent users from an empty store returns an empty list

These tests assert *lasting invariants* about the endpoint contract:
  - The response schema always contains ``users`` (list) and ``total`` (int).
  - The ``users`` list is always ordered by ``created_at`` descending.
  - Invalid ``limit`` values always produce HTTP 400 with a ``detail`` string.
  - The ``total`` field always equals the full store count, never the
    truncated count.

Boundary pins (no other task in this feature will implement these):
  - The ``validate_limit`` function in ``src/users/validators.py`` is the
    sole authority for limit validation.  Tests assert its contract
    (positive integer, max 100) rather than any specific error message.
"""

from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import UserCreate


class TestRecentUsersAcceptance:
    """Acceptance tests for GET /recent-users covering all 9 scenarios."""

    # ------------------------------------------------------------------
    # SC-09: Empty store returns an empty list
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sc09_empty_store_returns_empty_list(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """SC-09: Requesting recent users from an empty store returns an empty list.

        Invariant: The response has status 200 with ``users=[]`` and ``total=0``.
        """
        response = await async_client.get("/recent-users")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["users"] == []
        assert data["total"] == 0

    # ------------------------------------------------------------------
    # SC-01: Default limit returns 10 users
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sc01_default_limit_returns_ten_users(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """SC-01: Requesting recent users without a limit returns the default
        number of newest users.

        Invariant: When the store has >= 10 users, the response contains
        exactly 10 users ordered by ``created_at`` descending, and ``total``
        reflects the full store count.
        """
        # Seed 15 users so the default limit is exercised (not truncated).
        for i in range(15):
            await crud.create_user(
                db_session,
                UserCreate(
                    email=f"sc01_user{i}@example.com", full_name=f"SC01 User {i}"
                ),
            )
        await db_session.commit()

        response = await async_client.get("/recent-users")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data["users"]) == 10
        assert data["total"] == 15
        # Invariant: newest-first ordering
        timestamps = [u["created_at"] for u in data["users"]]
        assert timestamps == sorted(timestamps, reverse=True)

    # ------------------------------------------------------------------
    # SC-02: Valid explicit limit returns that many users
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sc02_explicit_limit_returns_that_many_users(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """SC-02: Requesting recent users with a valid explicit limit returns
        that many newest users.

        Invariant: The response contains exactly ``limit`` users ordered by
        ``created_at`` descending, and ``total`` reflects the full store count.
        """
        for i in range(20):
            await crud.create_user(
                db_session,
                UserCreate(
                    email=f"sc02_user{i}@example.com", full_name=f"SC02 User {i}"
                ),
            )
        await db_session.commit()

        response = await async_client.get("/recent-users?limit=7")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data["users"]) == 7
        assert data["total"] == 20
        timestamps = [u["created_at"] for u in data["users"]]
        assert timestamps == sorted(timestamps, reverse=True)

    # ------------------------------------------------------------------
    # SC-03: Maximum allowed limit (100) returns that many users
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sc03_maximum_limit_returns_that_many_users(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """SC-03: Requesting recent users at the maximum allowed limit returns
        that many users.

        Invariant: When the store has >= 100 users and limit=100, the response
        contains exactly 100 users ordered by ``created_at`` descending.
        """
        for i in range(100):
            await crud.create_user(
                db_session,
                UserCreate(
                    email=f"sc03_user{i}@example.com",
                    full_name=f"SC03 User {i}",
                ),
            )
        await db_session.commit()

        response = await async_client.get("/recent-users?limit=100")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data["users"]) == 100
        assert data["total"] == 100
        timestamps = [u["created_at"] for u in data["users"]]
        assert timestamps == sorted(timestamps, reverse=True)

    # ------------------------------------------------------------------
    # SC-04: Limit exceeding maximum is rejected (400)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sc04_limit_exceeding_maximum_rejected(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """SC-04: Requesting recent users with a limit exceeding the maximum is
        rejected.

        Invariant: A limit > 100 always produces HTTP 400.
        """
        response = await async_client.get("/recent-users?limit=101")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)

    # ------------------------------------------------------------------
    # SC-05: Limit of 1 returns a single newest user
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sc05_limit_one_returns_single_user(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """SC-05: Requesting recent users with a limit of 1 returns a single
        newest user.

        Invariant: The response contains exactly 1 user, and ``total``
        reflects the full store count.
        """
        for i in range(5):
            await crud.create_user(
                db_session,
                UserCreate(
                    email=f"sc05_user{i}@example.com", full_name=f"SC05 User {i}"
                ),
            )
        await db_session.commit()

        response = await async_client.get("/recent-users?limit=1")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data["users"]) == 1
        assert data["total"] == 5
        assert "created_at" in data["users"][0]

    # ------------------------------------------------------------------
    # SC-06: Limit of zero is rejected (400)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sc06_limit_zero_rejected(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """SC-06: Requesting recent users with a limit of zero is rejected.

        Invariant: A limit of 0 always produces HTTP 400.
        """
        response = await async_client.get("/recent-users?limit=0")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)

    # ------------------------------------------------------------------
    # SC-07: Negative limit is rejected (400)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sc07_negative_limit_rejected(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """SC-07: Requesting recent users with a negative limit is rejected.

        Invariant: A negative limit always produces HTTP 400.
        """
        response = await async_client.get("/recent-users?limit=-1")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)

    # ------------------------------------------------------------------
    # SC-08: Non-integer limit is rejected (400)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sc08_non_integer_limit_rejected(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """SC-08: Requesting recent users with a non-integer limit is rejected.

        Invariant: A non-integer limit (float, string) always produces HTTP 400.
        """
        response = await async_client.get("/recent-users?limit=abc")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)

    # ------------------------------------------------------------------
    # Additional invariant: response schema always has required fields
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_response_schema_has_required_fields(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Invariant: Every successful response contains ``users`` (list) and
        ``total`` (int).

        This is a lasting contract invariant — not a point-in-time snapshot.
        """
        await crud.create_user(
            db_session,
            UserCreate(email="schema@example.com", full_name="Schema Test"),
        )
        await db_session.commit()

        response = await async_client.get("/recent-users")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert isinstance(data["users"], list)
        assert isinstance(data["total"], int)

        # Each user must have the standard fields.
        for user in data["users"]:
            assert "id" in user
            assert "email" in user
            assert "full_name" in user
            assert "is_active" in user
            assert "created_at" in user
            assert "updated_at" in user
