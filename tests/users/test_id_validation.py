"""Tests for ID validation at the router level."""

from __future__ import annotations

from http import HTTPStatus
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import UserCreate


class TestGetUserIdValidation:
    """Tests for GET /users/{id} ID validation."""

    @pytest.mark.asyncio
    async def test_empty_id_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/ with empty segment should return 400 (AC-001, AC-003)."""
        response = await async_client.get("/users/")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_at_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with @ character should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user@id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data
        assert "invalid characters" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_special_chars_hash_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with # character should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user#id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_slash_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with / character should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user/id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_dot_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with . character should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user.id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_space_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with space should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user%20id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_pipe_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with | character should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user|id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_semicolon_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with ; character should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user;id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_colon_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with : character should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user:id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_quotes_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with double quotes should return 400 (AC-002, AC-003)."""
        response = await async_client.get('/users/user"id')

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_angle_brackets_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with angle brackets should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user<id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_brackets_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with brackets should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user[id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_curly_braces_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with curly braces should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user{id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_plus_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with + character should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user+id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_equals_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with = character should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user=id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_comma_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with comma should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user,id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_question_mark_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with ? character should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user?id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_tilde_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with ~ character should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user~id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_caret_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with ^ character should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user^id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_exclamation_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with ! character should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user!id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_percent_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with % character should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user%id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_dollar_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with $ character should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user$id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_ampersand_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with & character should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user&id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_asterisk_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with * character should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user*id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_backslash_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with \\ character should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user\\id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_newline_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with newline should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user\nid")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_tab_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with tab should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user\tid")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_parentheses_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id} with parentheses should return 400 (AC-002, AC-003)."""
        response = await async_client.get("/users/user(id")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_valid_uuid_returns_404_not_400(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """Valid UUID format that doesn't exist should return 404, not 400."""
        fake_id = str(uuid4())

        response = await async_client.get(f"/users/{fake_id}")

        # Should be 404 (not found), not 400 (bad request)
        assert response.status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_valid_uuid_returns_200_for_existing_user(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Valid UUID for existing user should return 200."""
        user_in = UserCreate(
            email="validation-test@example.com",
            full_name="Validation Test",
        )
        created = await crud.create_user(db_session, user_in)

        response = await async_client.get(f"/users/{created.id}")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["id"] == created.id
        assert data["email"] == "validation-test@example.com"


class TestGetUserSummaryIdValidation:
    """Tests for GET /users/{id}/summary ID validation."""

    @pytest.mark.asyncio
    async def test_empty_id_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users//summary with empty segment should return 400."""
        response = await async_client.get("/users//summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_at_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with @ should return 400."""
        response = await async_client.get("/users/user@id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_hash_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with # should return 400."""
        response = await async_client.get("/users/user#id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_slash_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with / should return 400."""
        response = await async_client.get("/users/user/id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_dot_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with . should return 400."""
        response = await async_client.get("/users/user.id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_pipe_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with | should return 400."""
        response = await async_client.get("/users/user|id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_semicolon_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with ; should return 400."""
        response = await async_client.get("/users/user;id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_colon_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with : should return 400."""
        response = await async_client.get("/users/user:id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_plus_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with + should return 400."""
        response = await async_client.get("/users/user+id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_equals_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with = should return 400."""
        response = await async_client.get("/users/user=id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_comma_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with , should return 400."""
        response = await async_client.get("/users/user,id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_question_mark_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with ? should return 400."""
        response = await async_client.get("/users/user?id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_tilde_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with ~ should return 400."""
        response = await async_client.get("/users/user~id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_caret_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with ^ should return 400."""
        response = await async_client.get("/users/user^id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_exclamation_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with ! should return 400."""
        response = await async_client.get("/users/user!id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_percent_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with % should return 400."""
        response = await async_client.get("/users/user%id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_dollar_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with $ should return 400."""
        response = await async_client.get("/users/user$id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_ampersand_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with & should return 400."""
        response = await async_client.get("/users/user&id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_asterisk_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with * should return 400."""
        response = await async_client.get("/users/user*id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_backslash_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with \\ should return 400."""
        response = await async_client.get("/users/user\\id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_newline_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with newline should return 400."""
        response = await async_client.get("/users/user\nid/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_tab_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with tab should return 400."""
        response = await async_client.get("/users/user\tid/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_parentheses_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with () should return 400."""
        response = await async_client.get("/users/user(id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_brackets_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with [] should return 400."""
        response = await async_client.get("/users/user[id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_curly_braces_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with {} should return 400."""
        response = await async_client.get("/users/user{id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_angle_brackets_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with <> should return 400."""
        response = await async_client.get("/users/user<id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_space_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with space should return 400."""
        response = await async_client.get("/users/user%20id/summary")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_special_chars_quotes_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /users/{id}/summary with " should return 400."""
        response = await async_client.get('/users/user"id/summary')

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data
