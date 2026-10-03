"""End-to-end scenarios for ``GET /users/active-count`` (FEAT-651C).

These are the four examples in
``features/active-count-endpoint/active-count-endpoint.feature``, run through
the application: the users are put in the data store with the same HTTP surface
any caller uses, and the counts are read back from the endpoint itself. The
database behind the request is the real one, reached through the
``override_get_db`` override, so the SQL that splits the population really
executes rather than a stand-in for it.

What the other tasks in this feature own is deliberately not re-pinned here:
the split query belongs to ``tests/users/test_active_count_crud.py``
(TASK-651C-002), the response schema to ``tests/users/test_schemas.py``
(TASK-651C-001), and the route's own contract — status, body shape, 503 on a
database failure — to ``tests/users/test_active_count_endpoint.py``
(TASK-651C-003). What is asserted below is the scenario at the surface: that
the numbers a caller gets are the state of the store.
"""

from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient

ACTIVE_COUNT_PATH = "/users/active-count"

# Paths that answer to no route in the application at all, so anything other
# than 404 on them would mean the endpoint is reachable under a name nobody
# registered. ``/users/<word>`` is not in this list: there the segment is a
# user id, not a path, and ``/users/{user_id}`` has its own tests.
PATHS_WITH_NO_ROUTE = (
    "/active-count",
    "/users/active-count/",
    "/users/active-count/extra",
    "/users/count/active-count",
)


async def _seed_users(async_client: AsyncClient, *, active: int, inactive: int) -> None:
    """Put a known number of active and inactive users in the data store.

    Creation and the flag are both set through the application's own endpoints,
    so the store reaches the state a real caller would have left it in rather
    than one written straight into a table.

    Args:
        async_client: The client bound to the application under test.
        active: How many users to leave flagged active.
        inactive: How many users to create and then flag inactive.
    """
    for n in range(active):
        created = await async_client.post(
            "/users", json={"email": f"active-{n}@example.com"}
        )
        assert created.status_code == HTTPStatus.CREATED

    for n in range(inactive):
        created = await async_client.post(
            "/users", json={"email": f"inactive-{n}@example.com"}
        )
        assert created.status_code == HTTPStatus.CREATED
        turned_off = await async_client.put(
            f"/users/{created.json()['id']}", json={"is_active": False}
        )
        assert turned_off.status_code == HTTPStatus.OK


class TestActiveCountScenarios:
    """The feature's examples, at the HTTP surface."""

    async def test_active_count_matches_the_active_users(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """A non-empty store reports exactly its active users."""
        await _seed_users(async_client, active=3, inactive=1)

        response = await async_client.get(ACTIVE_COUNT_PATH)

        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert body["active_count"] == 3
        assert isinstance(body["active_count"], int)
        assert body["active_count"] >= 0

    async def test_inactive_count_matches_the_inactive_users(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """A non-empty store reports exactly its inactive users."""
        await _seed_users(async_client, active=2, inactive=4)

        response = await async_client.get(ACTIVE_COUNT_PATH)

        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert body["inactive_count"] == 4
        assert isinstance(body["inactive_count"], int)
        assert body["inactive_count"] >= 0

    async def test_the_two_counts_are_reported_together(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """One request answers both states, and no other state exists."""
        await _seed_users(async_client, active=2, inactive=1)

        assert (await async_client.get(ACTIVE_COUNT_PATH)).json() == {
            "active_count": 2,
            "inactive_count": 1,
        }

    async def test_both_counts_are_zero_when_no_users_exist(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """An empty store yields 0 for both counts, not a missing key or a 404."""
        assert (await async_client.get("/users/count")).json() == {"count": 0}

        response = await async_client.get(ACTIVE_COUNT_PATH)

        assert response.status_code == HTTPStatus.OK
        assert response.json() == {"active_count": 0, "inactive_count": 0}


class TestActiveCountRejectsWhatItIsNot:
    """The endpoint is a read of one exact path, and nothing else."""

    async def test_post_is_rejected(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """POST has no handler here: 405, saying which methods the path takes."""
        response = await async_client.post(
            ACTIVE_COUNT_PATH, json={"email": "nobody@example.com"}
        )

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
        assert "GET" in response.headers.get("allow", "")

    async def test_a_refused_post_creates_no_user(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Refusing the write is real: the store is left as it was."""
        await _seed_users(async_client, active=1, inactive=0)

        await async_client.post(ACTIVE_COUNT_PATH, json={"email": "nobody@example.com"})

        assert (await async_client.get("/users/count")).json() == {"count": 1}
        assert (await async_client.get(ACTIVE_COUNT_PATH)).json() == {
            "active_count": 1,
            "inactive_count": 0,
        }

    @pytest.mark.parametrize("path", PATHS_WITH_NO_ROUTE)
    async def test_a_path_that_is_not_the_endpoint_is_rejected(
        self, async_client: AsyncClient, override_get_db: None, path: str
    ) -> None:
        """No spelling of a near-miss answers with counts."""
        response = await async_client.get(path)

        assert response.status_code == HTTPStatus.NOT_FOUND
