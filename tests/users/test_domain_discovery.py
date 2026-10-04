"""GET /users/domains, answered at the surface a caller uses.

Every test here asks the running application through httpx rather than calling
the query underneath it, so what is asserted is the answer a person gets. The
four cases are the four examples of
features/user-domain-discovery/user-domain-discovery.feature:

  AC-001: a request returns a sorted list of the distinct domains
  AC-002: with no users the answer is an empty list, and still a success
  AC-003: an address with no usable domain part contributes nothing
  AC-004: requests made at the same time all succeed with the same list

Each test runs against a database of its own (see tests/conftest.py), so the
rows one test writes are not there for the next one to find, and no test
depends on rows another one left behind.

The rows are written with the ``seed_user_row`` fixture rather than through
``POST /users``: what is being read is the point of these tests, not how the
rows got there, and the malformed addresses of AC-003 could not be written
through the creation schema at all — it validates the address first.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from http import HTTPStatus

from httpx import AsyncClient

from src.users.models import User

DOMAINS_PATH = "/users/domains"


class TestSortedDistinctDomains:
    """AC-001: one entry per domain, in alphabetical order."""

    async def test_returns_each_domain_once_in_alphabetical_order(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        seed_user_row: Callable[..., Awaitable[User]],
    ) -> None:
        """Four domains, one of them shared, come back once each and sorted.

        The rows go in with the domains in reverse order, so an answer that
        leaked the store's row order would fail rather than pass by luck.
        """
        await seed_user_row("carol@zeta.example", full_name="Carol")
        await seed_user_row("dave@mid.example", full_name="Dave")
        await seed_user_row("erin@beta.example", full_name="Erin")
        await seed_user_row("bob@beta.example", full_name="Bob")
        await seed_user_row("alice@alpha.example", full_name="Alice")

        response = await async_client.get(DOMAINS_PATH)

        assert response.status_code == HTTPStatus.OK
        assert response.json() == [
            "alpha.example",
            "beta.example",
            "mid.example",
            "zeta.example",
        ]

    async def test_the_list_is_a_json_array_with_no_repeated_entry(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        seed_user_row: Callable[..., Awaitable[User]],
    ) -> None:
        """The body is an array of strings, sorted and free of duplicates."""
        await seed_user_row("gina@example.com")
        await seed_user_row("hank@example.com")
        await seed_user_row("iris@example.com")
        await seed_user_row("jack@other.org")

        response = await async_client.get(DOMAINS_PATH)

        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert isinstance(body, list)
        assert all(isinstance(domain, str) for domain in body)
        assert len(body) == len(set(body))
        assert body == sorted(body)

    async def test_one_domain_written_two_ways_is_one_entry(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        seed_user_row: Callable[..., Awaitable[User]],
    ) -> None:
        """The same domain written upper-case and lower-case is one entry."""
        await seed_user_row("User@Example.COM", full_name="Upper")
        await seed_user_row("user@example.com", full_name="Lower")

        response = await async_client.get(DOMAINS_PATH)

        assert response.status_code == HTTPStatus.OK
        assert response.json() == ["example.com"]


class TestEmptyDomainList:
    """AC-002: no users is a working answer, not an error."""

    async def test_returns_an_empty_list_when_no_users_exist(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """An empty store answers 200 with an empty array."""
        response = await async_client.get(DOMAINS_PATH)

        assert response.status_code == HTTPStatus.OK
        assert response.json() == []

    async def test_the_empty_answer_is_an_array_rather_than_a_missing_value(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """Nothing users is a list of length zero, not null and not a 404."""
        response = await async_client.get(DOMAINS_PATH)

        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 0


class TestMalformedAddresses:
    """AC-003: an address with no domain part is not a domain."""

    async def test_addresses_with_no_domain_part_contribute_nothing(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        seed_user_row: Callable[..., Awaitable[User]],
    ) -> None:
        """The usable address is reported; the unusable ones add no entry."""
        await seed_user_row("not-an-email", full_name="No At Sign")
        await seed_user_row("also not an email", full_name="Spaces")
        await seed_user_row("missing-part@", full_name="Nothing After")
        await seed_user_row("anna@example.com", full_name="Anna")

        response = await async_client.get(DOMAINS_PATH)

        assert response.status_code == HTTPStatus.OK
        assert response.json() == ["example.com"]

    async def test_a_store_of_only_unusable_addresses_answers_an_empty_list(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        seed_user_row: Callable[..., Awaitable[User]],
    ) -> None:
        """Malformed rows alone do not turn the request into an error."""
        await seed_user_row("no-at-sign", full_name="First")
        await seed_user_row("nobody@no-dot-here", full_name="Second")

        response = await async_client.get(DOMAINS_PATH)

        assert response.status_code == HTTPStatus.OK
        assert response.json() == []


class TestConcurrentRequests:
    """AC-004: requests made at the same time all answer the same thing."""

    async def test_requests_made_at_the_same_time_all_answer_the_same_list(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        seed_user_row: Callable[..., Awaitable[User]],
    ) -> None:
        """Four simultaneous requests: four 200s, one and the same array."""
        await seed_user_row("one@example.com")
        await seed_user_row("two@example.com")
        await seed_user_row("three@other.org")

        responses = await asyncio.gather(
            *(async_client.get(DOMAINS_PATH) for _ in range(4))
        )

        assert [r.status_code for r in responses] == [HTTPStatus.OK] * 4
        bodies = [r.json() for r in responses]
        assert all(body == ["example.com", "other.org"] for body in bodies)

    async def test_a_simultaneous_answer_matches_a_sequential_one(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        seed_user_row: Callable[..., Awaitable[User]],
    ) -> None:
        """Reading at the same time says what reading one after the other says."""
        await seed_user_row("zoe@zulu.example")
        await seed_user_row("mia@india.example")

        simultaneous, sequential = await asyncio.gather(
            async_client.get(DOMAINS_PATH),
            async_client.get(DOMAINS_PATH),
        )

        assert simultaneous.status_code == HTTPStatus.OK
        assert sequential.status_code == HTTPStatus.OK
        assert (
            simultaneous.json()
            == sequential.json()
            == [
                "india.example",
                "zulu.example",
            ]
        )
