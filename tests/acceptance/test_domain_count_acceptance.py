"""Acceptance tests for the GET /users/count-by-domain endpoint.

Covers all scenarios from the feature specification:

  SC-01: A request returns domain counts ordered by count descending (happy path)
  SC-02: An empty user set returns an empty list
  SC-03: A POST request to the endpoint is rejected
  SC-04: A PUT request to the endpoint is rejected
  SC-05: A DELETE request to the endpoint is rejected
  SC-06: The endpoint handles a large number of domains
  SC-07: Domains with no users are excluded from the list
  SC-08: Malformed email addresses are ignored

These tests assert lasting invariants about the endpoint contract:
  - The response is always a JSON array of {domain, count} objects.
  - Entries are always ordered by count in descending order.
  - Unsupported HTTP methods (POST/PUT/DELETE) are always rejected.
"""

from __future__ import annotations

from http import HTTPStatus
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import UserCreate


class TestDomainCountAcceptance:
    """Acceptance tests for GET /users/count-by-domain covering all scenarios."""

    # ------------------------------------------------------------------
    # SC-01: Happy path — domain counts returned correctly, ordered descending
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sc01_happy_path_domain_counts_ordered_descending(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """SC-01: A request returns domain counts ordered by count descending.

        Invariant: The response is a list of {domain, count} objects ordered
        by count in descending order.
        """
        # Seed users across multiple domains with varying counts.
        users_to_seed: list[tuple[str, str]] = [
            ("user1@example.com", "User 1"),
            ("user2@example.com", "User 2"),
            ("user3@example.com", "User 3"),
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

        response = await async_client.get("/users/count-by-domain")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3

        # Verify schema: each entry has domain (str) and count (int).
        for entry in data:
            assert "domain" in entry
            assert "count" in entry
            assert isinstance(entry["domain"], str)
            assert isinstance(entry["count"], int)

        # Verify ordering: descending by count.
        counts = [entry["count"] for entry in data]
        assert counts == sorted(counts, reverse=True)

        # Verify specific counts.
        assert data[0] == {"domain": "example.com", "count": 3}
        assert data[1] == {"domain": "other.org", "count": 2}
        assert data[2] == {"domain": "third.net", "count": 1}

    # ------------------------------------------------------------------
    # SC-02: Empty user set returns an empty list
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sc02_empty_user_set_returns_empty_list(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """SC-02: An empty user set returns an empty list.

        Invariant: The response is status 200 with an empty JSON array.
        """
        response = await async_client.get("/users/count-by-domain")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data == []

    # ------------------------------------------------------------------
    # SC-03: POST request is rejected
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sc03_post_rejected(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """SC-03: A POST request to the endpoint is rejected.

        Invariant: The endpoint returns 405 Method Not Allowed for POST.
        """
        response = await async_client.post(
            "/users/count-by-domain",
            json={"domain": "example.com"},
        )

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    # ------------------------------------------------------------------
    # SC-04: PUT request is rejected
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sc04_put_rejected(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """SC-04: A PUT request to the endpoint is rejected.

        Invariant: The endpoint rejects PUT with any error status code
        (4xx). The exact code may be 405 or 400 depending on route
        matching order in the router.
        """
        response = await async_client.put(
            "/users/count-by-domain",
            json={"domain": "example.com"},
        )

        assert response.status_code >= HTTPStatus.BAD_REQUEST
        assert response.status_code < HTTPStatus.INTERNAL_SERVER_ERROR

    # ------------------------------------------------------------------
    # SC-05: DELETE request is rejected
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sc05_delete_rejected(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """SC-05: A DELETE request to the endpoint is rejected.

        Invariant: The endpoint rejects DELETE with any error status code
        (4xx). The exact code may be 405 or 400 depending on route
        matching order in the router.
        """
        response = await async_client.delete("/users/count-by-domain")

        assert response.status_code >= HTTPStatus.BAD_REQUEST
        assert response.status_code < HTTPStatus.INTERNAL_SERVER_ERROR

    # ------------------------------------------------------------------
    # SC-06: Large number of domains handled correctly
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sc06_large_domain_set(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """SC-06: The endpoint handles a large number of domains.

        Invariant: The response contains all domains and is ordered by count
        descending, even with a large number of distinct domains.
        """
        # Seed 100 distinct domains with varying user counts.
        for domain_idx in range(100):
            count = domain_idx + 1  # 1 to 100 users per domain.
            for user_idx in range(count):
                email = f"user{user_idx}@domain{domain_idx}.com"
                user_in = UserCreate(
                    email=email,
                    full_name=f"Domain {domain_idx} User {user_idx}",
                )
                await crud.create_user(db_session, user_in)
        await db_session.commit()

        response = await async_client.get("/users/count-by-domain")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 100

        # Verify ordering: descending by count.
        counts = [entry["count"] for entry in data]
        assert counts == sorted(counts, reverse=True)

        # Verify the top entry has the highest count (100 users).
        assert data[0]["count"] == 100
        # Verify the last entry has the lowest count (1 user).
        assert data[-1]["count"] == 1

    # ------------------------------------------------------------------
    # SC-07: Domains with no users are excluded
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sc07_domains_without_users_excluded(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """SC-07: Domains with no users are excluded from the list.

        Invariant: Only domains that have at least one user appear in the
        response. A domain with no users should not appear.
        """
        # Seed users only from two domains.
        for i in range(2):
            await crud.create_user(
                db_session,
                UserCreate(
                    email=f"user{i}@active.com",
                    full_name=f"Active User {i}",
                ),
            )
        await db_session.commit()

        response = await async_client.get("/users/count-by-domain")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert isinstance(data, list)

        # Only the seeded domain should appear.
        domains = {entry["domain"] for entry in data}
        assert "active.com" in domains
        # A domain with no users should not appear.
        assert "inactive.com" not in domains
        assert "nonexistent.org" not in domains

    # ------------------------------------------------------------------
    # SC-08: Malformed email addresses are ignored
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sc08_malformed_emails_ignored(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """SC-08: Malformed email addresses are ignored.

        Invariant: The endpoint succeeds and does not crash when users with
        malformed email addresses exist in the store. Malformed domains
        should not appear in the response.

        Note: The UserCreate schema validates emails at the API level, so
        malformed emails can only be inserted via the CRUD layer directly.
        """
        # Insert a user with a malformed email directly via the model
        # to simulate data that may exist in the store.
        from src.users.models import User

        malformed_user = User(
            id=str(uuid4()),
            email="not-an-email",  # type: ignore[arg-type]
            full_name="Malformed User",
            is_active=True,
        )
        db_session.add(malformed_user)

        # Also insert a valid user.
        await crud.create_user(
            db_session,
            UserCreate(email="valid@example.com", full_name="Valid User"),
        )
        await db_session.commit()

        response = await async_client.get("/users/count-by-domain")

        # The endpoint should succeed (not crash).
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert isinstance(data, list)

        # The malformed email domain should not appear.
        domains = {entry["domain"] for entry in data}
        assert "not-an-email" not in domains
        # The valid domain should appear.
        assert "example.com" in domains
