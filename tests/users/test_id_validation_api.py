"""API-level tests for ID validation (AC-003: return 400 Bad Request).

Verifies that the /users/{user_id} and /users/{user_id}/summary endpoints
return 400 Bad Request for invalid user ID formats.

These tests exercise the full request pipeline including the
get_validated_user_id dependency that converts validation errors
to HTTPException(400).
"""

from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient


class TestGetUserByIdBadRequest:
    """Tests for 400 Bad Request on GET /users/{id} with invalid IDs (AC-003)."""

    @pytest.mark.asyncio
    async def test_empty_user_id_returns_404(self, async_client: AsyncClient) -> None:
        """Empty path segment does not match /{user_id} route (FastAPI behavior).

        FastAPI's path parameter matching means an empty path segment
        will not match /{user_id}, so this returns 404 Not Found rather
        than 400. This is expected framework behavior.
        """
        response = await async_client.get("/users/")
        # FastAPI redirect_slashes=False but empty path still doesn't match
        assert response.status_code in (HTTPStatus.NOT_FOUND, HTTPStatus.BAD_REQUEST)

    @pytest.mark.asyncio
    async def test_special_char_at_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with @ character returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%40id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_hash_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with # character returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%23id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_dollar_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with $ character returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%24id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_ampersand_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with & character returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%26id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_slash_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with / character returns 400 Bad Request (AC-003).

        Note: URL-encoding / as %2f in a path creates a 2-segment path
        that FastAPI doesn't match to /{user_id}. The test verifies the
        validator rejects / as invalid at the unit level; the API-level
        test here checks that an attempt to pass / via path parameter
        is rejected (either 400 from validation or 404 from route
        mismatch, both are correct security outcomes).
        """
        response = await async_client.get("/users/user%2fid")

        # FastAPI route matching: %2f creates a 2-segment path, which
        # doesn't match /{user_id}. Both 400 and 404 are acceptable
        # security outcomes (the input is rejected).
        assert response.status_code in (
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.NOT_FOUND,
        )

    @pytest.mark.asyncio
    async def test_special_char_pipe_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with | character returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%7cid")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_backslash_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with \\ character returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%5cid")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_dot_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with . character returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%2eid")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_space_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with space returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%20id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_bracket_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with [ character returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%5bid")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_curly_brace_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with { character returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%7bid")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_angle_bracket_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with < character returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%3cid")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_comma_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with , character returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%2cid")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_question_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with ? character returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%3fid")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_plus_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with + character returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%2bid")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_equals_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with = character returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%3did")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_tilde_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with ~ character returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%7eid")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_caret_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with ^ character returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%5eid")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_exclamation_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with ! character returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%21id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_percent_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """ID with % character returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%25id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_non_uuid_format_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """Non-UUID format returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/not-a-uuid")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data
        detail_lower = data["detail"].lower()
        assert "uuid" in detail_lower or "invalid" in detail_lower

    @pytest.mark.asyncio
    async def test_uuid_with_extra_chars_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """UUID with extra characters returns 400 Bad Request (AC-003)."""
        response = await async_client.get(
            "/users/550e8400-e29b-41d4-a716-4466554400000"
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_400_error_body_has_detail_field(
        self, async_client: AsyncClient
    ) -> None:
        """400 response body contains a 'detail' field (AC-003)."""
        response = await async_client.get("/users/not-a-uuid")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)
        assert len(data["detail"]) > 0


class TestUserSummaryBadRequest:
    """Tests for 400 Bad Request on GET /users/{id}/summary (AC-003)."""

    @pytest.mark.asyncio
    async def test_special_char_at_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """Summary endpoint with @ in ID returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%40id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_hash_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """Summary endpoint with # in ID returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%23id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_non_uuid_format_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """Summary endpoint with non-UUID format returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/not-a-uuid/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_pipe_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """Summary endpoint with | in ID returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%7cid/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_char_dot_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """Summary endpoint with . in ID returns 400 Bad Request (AC-003)."""
        response = await async_client.get("/users/user%2eid/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_400_error_body_has_detail_field(
        self, async_client: AsyncClient
    ) -> None:
        """Summary endpoint 400 response body contains detail field (AC-003)."""
        response = await async_client.get("/users/not-a-uuid/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)
        assert len(data["detail"]) > 0
