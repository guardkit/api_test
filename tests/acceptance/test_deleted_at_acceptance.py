"""Acceptance tests for the `deleted_at` column on the users table.

Verifies the following acceptance criteria:

- AC-001: Test verifies `deleted_at` column existence and nullability
- AC-002: Test verifies user record can have null `deleted_at`
- AC-003: Test verifies user record can have non-null `deleted_at`
- AC-004: Test verifies `deleted_at` column is not a boolean type
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.users import crud
from src.users.models import User
from src.users.schemas import UserCreate


class TestDeletedAtColumnExistence:
    """AC-001: Verify `deleted_at` column exists and is nullable in the schema."""

    async def test_deleted_at_column_exists_in_table(
        self, db_engine: AsyncEngine
    ) -> None:
        """Verify the deleted_at column exists in the users table schema."""
        async with db_engine.begin() as conn:
            await conn.run_sync(User.metadata.create_all)

        async with db_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA table_info(users)"))
            columns = {row[1]: row for row in result.fetchall()}

        assert "deleted_at" in columns, (
            "The deleted_at column must exist in the users table"
        )

    async def test_deleted_at_column_is_nullable(self, db_engine: AsyncEngine) -> None:
        """Verify the deleted_at column allows NULL values at the schema level.

        In SQLite, PRAGMA table_info returns nullable as 1 for nullable columns.
        """
        async with db_engine.begin() as conn:
            await conn.run_sync(User.metadata.create_all)

        async with db_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA table_info(users)"))
            columns = {row[1]: row for row in result.fetchall()}

        deleted_at_info = columns["deleted_at"]
        # Column index 3 in PRAGMA table_info is 'notnull' (0 = nullable)
        assert deleted_at_info[3] == 0, (
            "The deleted_at column must be nullable (notnull=0)"
        )


class TestDeletedAtNullValue:
    """AC-002: Verify user record can have null `deleted_at`."""

    async def test_user_created_with_null_deleted_at(
        self, db_session: AsyncSession
    ) -> None:
        """A newly created user should have a null deleted_at."""
        user_in = UserCreate(email="null-deleted@example.com", full_name="NullDeleted")
        user = await crud.create_user(db_session, user_in)
        await db_session.flush()

        assert user.deleted_at is None, (
            "A newly created user must have deleted_at set to None"
        )

    async def test_user_with_null_deleted_at_retrievable(
        self, db_session: AsyncSession
    ) -> None:
        """A user with null deleted_at should be retrievable via get_user."""
        user_in = UserCreate(
            email="null-retrievable@example.com", full_name="NullRetrievable"
        )
        user = await crud.create_user(db_session, user_in)

        result = await crud.get_user(db_session, user.id)

        assert result is not None, "User with null deleted_at should be retrievable"
        assert result.deleted_at is None
        assert result.email == "null-retrievable@example.com"

    async def test_user_with_null_deleted_at_in_list(
        self, db_session: AsyncSession
    ) -> None:
        """A user with null deleted_at should appear in get_users results."""
        await crud.create_user(
            db_session,
            UserCreate(email="null-list@example.com", full_name="NullList"),
        )

        users = await crud.get_users(db_session)

        assert any(u.email == "null-list@example.com" for u in users), (
            "User with null deleted_at should appear in get_users"
        )


class TestDeletedAtNonNullValue:
    """AC-003: Verify user record can have non-null `deleted_at`."""

    async def test_user_can_have_non_null_deleted_at(
        self, db_session: AsyncSession
    ) -> None:
        """A user record should be able to store a non-null deleted_at timestamp."""
        user_in = UserCreate(
            email="non-null-deleted@example.com", full_name="NonNullDeleted"
        )
        user = await crud.create_user(db_session, user_in)

        deletion_time = datetime.now(UTC)
        user.deleted_at = deletion_time
        db_session.add(user)
        await db_session.flush()

        # Reload from database
        refreshed = await db_session.get(User, user.id)
        assert refreshed is not None
        assert refreshed.deleted_at is not None, (
            "deleted_at should be set to a non-null value"
        )
        assert refreshed.deleted_at.tzinfo is not None, (
            "deleted_at should preserve timezone info"
        )

    async def test_user_with_non_null_deleted_at_excluded_from_get_user(
        self, db_session: AsyncSession
    ) -> None:
        """A user with non-null deleted_at should not be returned by get_user."""
        user_in = UserCreate(email="excluded@example.com", full_name="Excluded")
        user = await crud.create_user(db_session, user_in)

        user.deleted_at = datetime.now(UTC)
        db_session.add(user)
        await db_session.flush()

        result = await crud.get_user(db_session, user.id)

        assert result is None, (
            "User with non-null deleted_at should not be returned by get_user"
        )

    async def test_user_with_non_null_deleted_at_excluded_from_get_users(
        self, db_session: AsyncSession
    ) -> None:
        """A user with non-null deleted_at should not appear in get_users results."""
        await crud.create_user(
            db_session,
            UserCreate(email="excluded-list@example.com", full_name="ExcludedList"),
        )

        deleted_user_in = UserCreate(
            email="excluded-deleted@example.com", full_name="ExcludedDeleted"
        )
        deleted_user = await crud.create_user(db_session, deleted_user_in)
        deleted_user.deleted_at = datetime.now(UTC)
        db_session.add(deleted_user)
        await db_session.flush()

        users = await crud.get_users(db_session)

        assert not any(u.email == "excluded-deleted@example.com" for u in users), (
            "Deleted user should not appear in get_users results"
        )


class TestDeletedAtNotBoolean:
    """AC-004: Verify `deleted_at` column is not a boolean type."""

    async def test_deleted_at_column_type_is_not_boolean(
        self, db_engine: AsyncEngine
    ) -> None:
        """Verify the deleted_at column is DateTime, not Boolean."""
        async with db_engine.begin() as conn:
            await conn.run_sync(User.metadata.create_all)

        # Inspect the column type via SQLAlchemy's reflection
        async with db_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA table_info(users)"))
            columns = {row[1]: row for row in result.fetchall()}

        # In SQLite PRAGMA, column type is at index 2
        column_type = columns["deleted_at"][2].lower()
        assert "boolean" not in column_type, (
            "deleted_at column must not be of Boolean type"
        )
        assert (
            "datetime" in column_type
            or "timestamp" in column_type
            or "time" in column_type
        ), "deleted_at column should be a DateTime/Time type"

    async def test_deleted_at_model_field_is_datetime_not_boolean(self) -> None:
        """Verify the SQLAlchemy model declares deleted_at as DateTime, not Boolean."""

        # The Python type annotation should be datetime, not bool
        type_annotation = User.__annotations__.get("deleted_at")
        assert type_annotation is not None, "deleted_at must have a type annotation"

        # Check the annotation contains datetime, not bool
        annotation_str = str(type_annotation)
        assert "datetime" in annotation_str or "None" in annotation_str, (
            "deleted_at type annotation should reference datetime, not bool"
        )
        assert "bool" not in annotation_str.lower(), (
            "deleted_at type annotation must not reference bool"
        )

    async def test_deleted_at_column_type_via_reflection(
        self, db_engine: AsyncEngine
    ) -> None:
        """Verify column type via SQLAlchemy table reflection."""
        result_holder: list[str] = []

        async with db_engine.begin() as conn:
            await conn.run_sync(User.metadata.create_all)

        async with db_engine.connect() as conn:
            from sqlalchemy import Table as SATable
            from sqlalchemy.schema import MetaData as _MetaData

            def _reflect(sync_conn: object) -> None:
                reflected_metadata = _MetaData()
                reflected_table = SATable(
                    "users",
                    reflected_metadata,
                    autoload_with=sync_conn,  # type: ignore[arg-type]
                )
                deleted_at_col = reflected_table.c.deleted_at
                result_holder.append(str(deleted_at_col.type))

            await conn.run_sync(_reflect)

        col_type = result_holder[0]

        assert "boolean" not in col_type.lower(), (
            f"Reflected column type '{col_type}' must not be Boolean"
        )
        assert "time" in col_type.lower(), (
            f"Reflected column type '{col_type}' should be DateTime/Time"
        )
