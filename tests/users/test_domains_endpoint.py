"""Tests for GET /users/domains and the query behind it.

Covers the acceptance criteria of the user-domain-discovery feature:

  AC-001: the endpoint returns a JSON array of unique domains
  AC-002: the domains come back in alphabetical order
  AC-003: an empty domain list is an empty array, not an error
  AC-004: two simultaneous requests both succeed, with the same answer

Plus the feature's negative example — an address with no domain part
contributes nothing to the list — and the CRUD function's own contract.
"""

from __future__ import annotations

import asyncio
from http import HTTPStatus
from unittest.mock import patch
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.main import app
from src.users import crud
from src.users.models import User
from src.users.schemas import UserCreate

DOMAINS_PATH = "/users/domains"


async def _seed_users(db: AsyncSession, *emails: str) -> None:
    """Store one live user per address, through the application's own CRUD."""
    for email in emails:
        await crud.create_user(db, UserCreate(email=email))
    await db.commit()


class TestDistinctDomainsCrud:
    """The query: distinct domains of live users, alphabetically."""

    # AC-003: no users, no domains
    async def test_no_users_yields_no_domains(self, db_session: AsyncSession) -> None:
        """With an empty table the answer is an empty list."""
        assert await crud.get_distinct_domains(db_session) == []

    # AC-001: one entry per domain, however many users share it
    async def test_domains_are_deduplicated(self, db_session: AsyncSession) -> None:
        """Three users on one domain produce one entry, not three."""
        await _seed_users(
            db_session,
            "one@example.com",
            "two@example.com",
            "three@example.com",
        )

        assert await crud.get_distinct_domains(db_session) == ["example.com"]

    # AC-002: alphabetical order
    async def test_domains_are_sorted(self, db_session: AsyncSession) -> None:
        """The list is alphabetical whatever order the rows come back in."""
        await _seed_users(
            db_session,
            "carol@zeta.example",
            "alice@beta.example",
            "bob@alpha.example",
            "dave@mid.example",
        )

        result = await crud.get_distinct_domains(db_session)

        assert result == [
            "alpha.example",
            "beta.example",
            "mid.example",
            "zeta.example",
        ]
        assert result == sorted(result)

    # ASSUM-001: a domain is one domain regardless of the case written
    async def test_case_is_folded_before_deduplication(
        self, db_session: AsyncSession
    ) -> None:
        """User@Example.COM and user@example.com are the same domain."""
        await _seed_users(db_session, "User@Example.COM", "user@example.com")

        assert await crud.get_distinct_domains(db_session) == ["example.com"]

    # The feature's negative example
    async def test_malformed_addresses_contribute_nothing(
        self, db_session: AsyncSession
    ) -> None:
        """An address with no domain part is not a domain."""
        db_session.add(
            User(
                id=str(uuid4()),
                email="not-an-email",
                full_name="Malformed",
                is_active=True,
            )
        )
        await _seed_users(db_session, "valid@example.com")

        result = await crud.get_distinct_domains(db_session)

        assert result == ["example.com"]
        assert "not-an-email" not in result

    # Soft-deleted users are out of every read in this module
    async def test_soft_deleted_users_are_excluded(
        self, db_session: AsyncSession
    ) -> None:
        """A domain whose only user was deleted is no longer a domain."""
        deleted = await crud.create_user(
            db_session, UserCreate(email="gone@retired.example")
        )
        await _seed_users(db_session, "staying@example.com")
        await crud.delete_user(db_session, str(deleted.id))

        assert await crud.get_distinct_domains(db_session) == ["example.com"]


class TestUserDomainsEndpoint:
    """GET /users/domains, exercised through the application."""

    # AC-001: a JSON array of unique domains
    async def test_returns_a_json_array_of_unique_domains(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """The response body is a JSON array with no repeated entry."""
        await _seed_users(
            db_session,
            "anna@example.com",
            "boris@example.com",
            "clara@other.org",
        )

        response = await async_client.get(DOMAINS_PATH)

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert isinstance(data, list)
        assert data == ["example.com", "other.org"]
        assert len(data) == len(set(data))

    # AC-002: alphabetical order, at the surface a person uses
    async def test_returns_domains_in_alphabetical_order(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """The array the caller receives is sorted, not the store's row order."""
        await _seed_users(
            db_session,
            "zoe@zulu.example",
            "mia@india.example",
            "liam@echo.example",
        )

        response = await async_client.get(DOMAINS_PATH)

        assert response.status_code == HTTPStatus.OK
        assert response.json() == ["echo.example", "india.example", "zulu.example"]

    # AC-003: the empty case is an empty array, and still a success
    async def test_returns_an_empty_array_when_no_users_exist(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """No users is a working answer, not a 404 and not a 500."""
        response = await async_client.get(DOMAINS_PATH)

        assert response.status_code == HTTPStatus.OK
        assert response.json() == []

    # AC-004: two requests at the same time
    async def test_concurrent_requests_both_succeed(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Two simultaneous requests both answer 200 with the same list."""
        await _seed_users(
            db_session,
            "one@example.com",
            "two@other.org",
        )

        first, second = await asyncio.gather(
            async_client.get(DOMAINS_PATH),
            async_client.get(DOMAINS_PATH),
        )

        assert first.status_code == HTTPStatus.OK
        assert second.status_code == HTTPStatus.OK
        assert first.json() == ["example.com", "other.org"]
        assert first.json() == second.json()

    # The literal path must not be swallowed by GET /users/{user_id}
    async def test_domains_is_not_answered_by_the_user_id_route(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """ ""domains" is the endpoint's name, not a malformed user ID."""
        response = await async_client.get(DOMAINS_PATH)

        assert response.status_code == HTTPStatus.OK
        assert isinstance(response.json(), list)

    # The operational failure every other read here translates the same way
    async def test_returns_503_when_the_database_is_unavailable(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """A database failure becomes a 503, not a traceback."""
        with patch.object(crud, "get_distinct_domains") as query:
            query.side_effect = SQLAlchemyError("Database connection failed")

            response = await async_client.get(DOMAINS_PATH)

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert "Database unavailable" in response.json()["detail"]

    # The contract is documented, not just working
    async def test_endpoint_is_documented(self) -> None:
        """The route appears in the OpenAPI document as a GET."""
        schema = app.openapi()
        assert "get" in schema["paths"][DOMAINS_PATH]
