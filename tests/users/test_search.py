"""Integration tests for the search API endpoint."""

from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import UserCreate


class TestSearchPartialNameMatch:
    """Tests for partial name matching in the search endpoint."""

    @pytest.mark.asyncio
    async def test_partial_name_match_returns_correct_users(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Test: partial name match returns correct users.

        Seeds several users with full names, then searches with a
        substring. Only users whose full name contains the substring
        should be returned.
        """
        await crud.create_user(db_session, UserCreate(
            email="alice@example.com", full_name="Alice Johnson"))
        await crud.create_user(db_session, UserCreate(
            email="bob@example.com", full_name="Bob Smith"))
        await crud.create_user(db_session, UserCreate(
            email="charlie@example.com", full_name="Charlie Brown"))

        response = await async_client.get("/search", params={"name": "ali"})
        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert body["query"] == "ali"
        assert body["total"] == 1
        assert "Alice Johnson" in body["results"]
        assert len(body["results"]) == 1

    @pytest.mark.asyncio
    async def test_partial_name_match_last_name(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Test that searching by last-name substring works."""
        await crud.create_user(db_session, UserCreate(
            email="john@example.com", full_name="John Doe"))
        await crud.create_user(db_session, UserCreate(
            email="jane@example.com", full_name="Jane Smith"))

        response = await async_client.get("/search", params={"name": "Doe"})
        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert body["total"] == 1
        assert "John Doe" in body["results"]


class TestSearchCaseInsensitive:
    """Tests for case-insensitive matching in the search endpoint."""

    @pytest.mark.asyncio
    async def test_case_insensitive_matching_works(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Test: case-insensitive matching works.

        Users with mixed-case names should match regardless of query
        case.
        """
        await crud.create_user(db_session, UserCreate(
            email="mary@example.com", full_name="Mary Jane Watson"))
        await crud.create_user(db_session, UserCreate(
            email="mike@example.com", full_name="Mike Ross"))

        response_upper = await async_client.get("/search", params={"name": "MARY"})
        assert response_upper.status_code == HTTPStatus.OK
        body_upper = response_upper.json()
        assert body_upper["total"] == 1
        assert "Mary Jane Watson" in body_upper["results"]

        response_mixed = await async_client.get("/search", params={"name": "MaRy"})
        assert response_mixed.status_code == HTTPStatus.OK
        body_mixed = response_mixed.json()
        assert body_mixed["total"] == 1
        assert "Mary Jane Watson" in body_mixed["results"]


class TestSearchEmptyQuery:
    """Tests for empty query handling in the search endpoint."""

    @pytest.mark.asyncio
    async def test_empty_query_returns_all_users(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Test: empty query returns all users.

        An empty string for the name parameter should return all users.
        """
        await crud.create_user(db_session, UserCreate(
            email="user1@example.com", full_name="First User"))
        await crud.create_user(db_session, UserCreate(
            email="user2@example.com", full_name="Second User"))
        await crud.create_user(db_session, UserCreate(
            email="user3@example.com", full_name="Third User"))

        response = await async_client.get("/search", params={"name": ""})
        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert body["query"] == ""
        assert body["total"] == 3
        assert len(body["results"]) == 3


class TestSearchSingleCharacter:
    """Tests for single character query handling."""

    @pytest.mark.asyncio
    async def test_single_character_query_works(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Test: single character query works.

        A single-character search term should return matching users.
        """
        await crud.create_user(db_session, UserCreate(
            email="anna@example.com", full_name="Anna Lee"))
        await crud.create_user(db_session, UserCreate(
            email="ben@example.com", full_name="Ben Carter"))
        await crud.create_user(db_session, UserCreate(
            email="carol@example.com", full_name="Carol White"))

        response = await async_client.get("/search", params={"name": "a"})
        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert body["query"] == "a"
        assert body["total"] == 3
        assert "Anna Lee" in body["results"]
        assert "Ben Carter" in body["results"]
        assert "Carol White" in body["results"]


class TestSearchNoMatches:
    """Tests for no-match scenarios in the search endpoint."""

    @pytest.mark.asyncio
    async def test_no_matches_returns_empty_list(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Test: no matches returns empty list.

        A query that matches no users should return an empty results
        list with total of 0.
        """
        await crud.create_user(db_session, UserCreate(
            email="alice@example.com", full_name="Alice Smith"))
        await crud.create_user(db_session, UserCreate(
            email="bob@example.com", full_name="Bob Jones"))

        response = await async_client.get("/search", params={"name": "zzzznotfound"})
        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert body["query"] == "zzzznotfound"
        assert body["results"] == []
        assert body["total"] == 0


class TestSearchSpecialCharacters:
    """Tests for special character handling in the search endpoint."""

    @pytest.mark.asyncio
    async def test_special_characters_handled_literally(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Test: special characters handled literally.

        Special characters in the query should be matched literally,
        not interpreted as SQL wildcards or regex operators.
        """
        await crud.create_user(db_session, UserCreate(
            email="special@example.com", full_name="John O'Brien"))
        await crud.create_user(db_session, UserCreate(
            email="percent@example.com", full_name="100% Complete"))
        await crud.create_user(db_session, UserCreate(
            email="quote@example.com", full_name='Mary "The Great" Smith'))
        await crud.create_user(db_session, UserCreate(
            email="normal@example.com", full_name="Normal User"))

        response_bang = await async_client.get("/search", params={"name": "O'Brien"})
        assert response_bang.status_code == HTTPStatus.OK
        body_bang = response_bang.json()
        assert body_bang["total"] == 1
        assert "John O'Brien" in body_bang["results"]

        response_percent = await async_client.get("/search", params={"name": "%"})
        assert response_percent.status_code == HTTPStatus.OK
        body_percent = response_percent.json()
        assert body_percent["total"] == 1
        assert "100% Complete" in body_percent["results"]


class TestSearchWhitespaceQuery:
    """Tests for whitespace-only query handling."""

    @pytest.mark.asyncio
    async def test_whitespace_only_query_returns_all_users(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Test: whitespace-only query returns all users.

        A query consisting only of whitespace should be treated as
        empty and return all users.
        """
        await crud.create_user(db_session, UserCreate(
            email="user1@example.com", full_name="First User"))
        await crud.create_user(db_session, UserCreate(
            email="user2@example.com", full_name="Second User"))

        response = await async_client.get("/search", params={"name": "   "})
        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert body["total"] == 2
        assert len(body["results"]) == 2
        assert "First User" in body["results"]
        assert "Second User" in body["results"]


class TestSearchMissingParameter:
    """Tests for missing parameter handling."""

    @pytest.mark.asyncio
    async def test_missing_parameter_returns_error(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test: missing parameter returns error.

        Calling the search endpoint without the required 'name' query
        parameter should return a 400 Bad Request error.
        """
        response = await async_client.get("/search")
        assert response.status_code == HTTPStatus.BAD_REQUEST

        body = response.json()
        assert "detail" in body
        detail = body["detail"].lower()
        assert "name" in detail
        assert "required" in detail

    @pytest.mark.asyncio
    async def test_missing_parameter_error_message_content(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test that the error message clearly indicates the required parameter."""
        response = await async_client.get("/search")
        assert response.status_code == HTTPStatus.BAD_REQUEST

        body = response.json()
        assert body["detail"] == "The 'name' query parameter is required"
