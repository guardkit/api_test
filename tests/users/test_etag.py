"""Tests for ETag integration with the GET /users/{user_id} endpoint."""

from __future__ import annotations

import asyncio
from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import UserCreate


class TestGetUserETag:
    """Tests for ETag header on GET /users/{user_id}."""

    @pytest.mark.asyncio
    async def test_get_user_includes_etag_header(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that GET /users/{user_id} returns an ETag header."""
        user_in = UserCreate(email="etag@example.com", full_name="ETag User")
        created = await crud.create_user(db_session, user_in)

        response = await async_client.get(f"/users/{created.id}")

        assert response.status_code == HTTPStatus.OK
        assert "ETag" in response.headers
        etag = response.headers["etag"]
        assert etag.startswith('"')
        assert etag.endswith('"')
        # ETag body is a SHA-256 hex digest (64 hex chars)
        digest = etag[1:-1]
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    @pytest.mark.asyncio
    async def test_etag_deterministic_for_same_user(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that the same user always returns the same ETag."""
        user_in = UserCreate(email="det@example.com", full_name="Deterministic")
        created = await crud.create_user(db_session, user_in)

        response1 = await async_client.get(f"/users/{created.id}")
        response2 = await async_client.get(f"/users/{created.id}")

        assert response1.headers["etag"] == response2.headers["etag"]

    @pytest.mark.asyncio
    async def test_etag_different_for_different_user(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that different users have different ETags."""
        user_a = UserCreate(email="diff-a@example.com", full_name="User A")
        user_b = UserCreate(email="diff-b@example.com", full_name="User B")
        created_a = await crud.create_user(db_session, user_a)
        created_b = await crud.create_user(db_session, user_b)

        resp_a = await async_client.get(f"/users/{created_a.id}")
        resp_b = await async_client.get(f"/users/{created_b.id}")

        assert resp_a.headers["etag"] != resp_b.headers["etag"]


class TestIfNoneMatch:
    """Tests for If-None-Match header handling on GET /users/{user_id}."""

    @pytest.mark.asyncio
    async def test_if_none_match_returns_304_when_etag_matches(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that If-None-Match with matching ETag returns 304 Not Modified."""
        user_in = UserCreate(email="304@example.com", full_name="304 User")
        created = await crud.create_user(db_session, user_in)

        # First request to get the ETag
        response1 = await async_client.get(f"/users/{created.id}")
        etag = response1.headers["etag"]

        # Second request with If-None-Match
        response2 = await async_client.get(
            f"/users/{created.id}",
            headers={"If-None-Match": etag},
        )

        assert response2.status_code == HTTPStatus.NOT_MODIFIED
        # 304 responses should not have a body
        assert response2.text == ""
        # ETag header should still be present
        assert "ETag" in response2.headers

    @pytest.mark.asyncio
    async def test_if_none_match_returns_200_when_etag_differs(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that If-None-Match with non-matching ETag returns 200."""
        user_in = UserCreate(email="200@example.com", full_name="200 User")
        created = await crud.create_user(db_session, user_in)

        fake_etag = '"0000000000000000000000000000000000000000000000000000000000000000"'

        response = await async_client.get(
            f"/users/{created.id}",
            headers={"If-None-Match": fake_etag},
        )

        assert response.status_code == HTTPStatus.OK
        assert "ETag" in response.headers
        data = response.json()
        assert data["email"] == "200@example.com"

    @pytest.mark.asyncio
    async def test_if_none_match_no_header_returns_200(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that GET without If-None-Match returns 200 with ETag."""
        user_in = UserCreate(email="noheader@example.com", full_name="No Header")
        created = await crud.create_user(db_session, user_in)

        response = await async_client.get(f"/users/{created.id}")

        assert response.status_code == HTTPStatus.OK
        assert "ETag" in response.headers

    @pytest.mark.asyncio
    async def test_etag_changes_after_user_update(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that ETag changes when user data is updated."""
        user_in = UserCreate(email="update-etag@example.com", full_name="Original Name")
        created = await crud.create_user(db_session, user_in)

        # Get initial ETag
        response1 = await async_client.get(f"/users/{created.id}")
        etag_before = response1.headers["etag"]

        # Update the user
        update_payload = {"full_name": "Updated Name"}
        await async_client.put(f"/users/{created.id}", json=update_payload)

        # Get new ETag
        response2 = await async_client.get(f"/users/{created.id}")
        etag_after = response2.headers["etag"]

        assert etag_before != etag_after

        # Old ETag should now return 200 (resource has changed)
        response3 = await async_client.get(
            f"/users/{created.id}",
            headers={"If-None-Match": etag_before},
        )
        assert response3.status_code == HTTPStatus.OK

        # New ETag should return 304 (resource matches)
        response4 = await async_client.get(
            f"/users/{created.id}",
            headers={"If-None-Match": etag_after},
        )
        assert response4.status_code == HTTPStatus.NOT_MODIFIED


class TestMalformedHeaders:
    """Tests for malformed If-None-Match header handling."""

    @pytest.mark.asyncio
    async def test_malformed_if_none_match_returns_200(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that a malformed If-None-Match header returns 200 with full resource."""
        user_in = UserCreate(email="malformed@example.com", full_name="Malformed User")
        created = await crud.create_user(db_session, user_in)

        response = await async_client.get(
            f"/users/{created.id}",
            headers={"If-None-Match": "not-a-valid-etag-at-all"},
        )

        assert response.status_code == HTTPStatus.OK
        assert "ETag" in response.headers
        data = response.json()
        assert data["email"] == "malformed@example.com"

    @pytest.mark.asyncio
    async def test_empty_if_none_match_returns_200(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that an empty If-None-Match header returns 200 with full resource."""
        user_in = UserCreate(email="empty@example.com", full_name="Empty User")
        created = await crud.create_user(db_session, user_in)

        response = await async_client.get(
            f"/users/{created.id}",
            headers={"If-None-Match": ""},
        )

        assert response.status_code == HTTPStatus.OK
        assert "ETag" in response.headers
        data = response.json()
        assert data["email"] == "empty@example.com"

    @pytest.mark.asyncio
    async def test_garbage_if_none_match_returns_200(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that a garbage If-None-Match header returns 200 with full resource."""
        user_in = UserCreate(email="garbage@example.com", full_name="Garbage User")
        created = await crud.create_user(db_session, user_in)

        response = await async_client.get(
            f"/users/{created.id}",
            headers={"If-None-Match": "<<<garbage>>>!!!@#$%"},
        )

        assert response.status_code == HTTPStatus.OK
        assert "ETag" in response.headers
        data = response.json()
        assert data["email"] == "garbage@example.com"

    @pytest.mark.asyncio
    async def test_if_none_match_star_returns_304(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that If-None-Match: * returns 304 when resource exists."""
        user_in = UserCreate(email="star@example.com", full_name="Star User")
        created = await crud.create_user(db_session, user_in)

        # If-None-Match: * matches any existing entity
        response2 = await async_client.get(
            f"/users/{created.id}",
            headers={"If-None-Match": "*"},
        )

        assert response2.status_code == HTTPStatus.NOT_MODIFIED
        assert response2.text == ""
        assert "ETag" in response2.headers

    @pytest.mark.asyncio
    async def test_if_none_match_multiple_etags_with_match(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that If-None-Match with multiple ETags returns 304 if one matches."""
        user_in = UserCreate(email="multi@example.com", full_name="Multi User")
        created = await crud.create_user(db_session, user_in)

        # Get the ETag
        response1 = await async_client.get(f"/users/{created.id}")
        etag = response1.headers["etag"]

        # Send multiple ETags including the matching one
        response2 = await async_client.get(
            f"/users/{created.id}",
            headers={"If-None-Match": f'"fake-etag-1", {etag}, "fake-etag-2"'},
        )

        assert response2.status_code == HTTPStatus.NOT_MODIFIED
        assert response2.text == ""
        assert "ETag" in response2.headers

    @pytest.mark.asyncio
    async def test_if_none_match_multiple_etags_no_match(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that If-None-Match with multiple ETags returns 200 if none match."""
        user_in = UserCreate(email="multi2@example.com", full_name="Multi2 User")
        created = await crud.create_user(db_session, user_in)

        # Get the ETag
        response1 = await async_client.get(f"/users/{created.id}")
        etag = response1.headers["etag"]

        # Send multiple ETags none of which match
        response2 = await async_client.get(
            f"/users/{created.id}",
            headers={"If-None-Match": '"fake-etag-1", "fake-etag-2", "fake-etag-3"'},
        )

        assert response2.status_code == HTTPStatus.OK
        assert "ETag" in response2.headers
        data = response2.json()
        assert data["email"] == "multi2@example.com"
        assert response2.headers["etag"] == etag


class TestConcurrentRequests:
    """Tests for concurrent request handling with ETags."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_same_etag_both_304(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that concurrent requests with the same ETag both return 304."""
        user_in = UserCreate(
            email="concurrent@example.com", full_name="Concurrent User"
        )
        created = await crud.create_user(db_session, user_in)

        # Get the ETag once
        response_initial = await async_client.get(f"/users/{created.id}")
        etag = response_initial.headers["etag"]

        # Fire multiple concurrent requests with the same ETag
        tasks = [
            async_client.get(f"/users/{created.id}", headers={"If-None-Match": etag})
            for _ in range(5)
        ]
        responses = await asyncio.gather(*tasks)

        # All concurrent requests should return 304
        for response in responses:
            assert response.status_code == HTTPStatus.NOT_MODIFIED
            assert "ETag" in response.headers
            assert response.text == ""

    @pytest.mark.asyncio
    async def test_concurrent_requests_without_etag_all_200(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that concurrent requests without If-None-Match all return 200."""
        user_in = UserCreate(email="noetag@example.com", full_name="No ETag User")
        created = await crud.create_user(db_session, user_in)

        tasks = [async_client.get(f"/users/{created.id}") for _ in range(5)]
        responses = await asyncio.gather(*tasks)

        for response in responses:
            assert response.status_code == HTTPStatus.OK
            assert "ETag" in response.headers
            data = response.json()
            assert data["email"] == "noetag@example.com"

    @pytest.mark.asyncio
    async def test_concurrent_mixed_etag_requests(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test mixed concurrent requests with matching and non-matching ETags."""
        user_in = UserCreate(email="mixed@example.com", full_name="Mixed User")
        created = await crud.create_user(db_session, user_in)

        # Get the current ETag
        response_initial = await async_client.get(f"/users/{created.id}")
        matching_etag = response_initial.headers["etag"]

        # Mix of matching and non-matching ETag requests
        tasks = [
            async_client.get(
                f"/users/{created.id}",
                headers={"If-None-Match": matching_etag},
            ),
            async_client.get(
                f"/users/{created.id}",
                headers={"If-None-Match": '"fake-fake-fake"'},
            ),
            async_client.get(
                f"/users/{created.id}",
                headers={"If-None-Match": matching_etag},
            ),
        ]
        responses = await asyncio.gather(*tasks)

        # Matching ETags should return 304, non-matching should return 200
        assert responses[0].status_code == HTTPStatus.NOT_MODIFIED
        assert responses[1].status_code == HTTPStatus.OK
        assert responses[2].status_code == HTTPStatus.NOT_MODIFIED
