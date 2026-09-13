"""Tests for the deleted_at column migration.

These tests verify:
- AC-001: Database migration adds `deleted_at` column to `users` table
- AC-002: `deleted_at` column is nullable
- AC-003: `deleted_at` column is of timestamp (DateTime) type
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from src.db.base import DeclarativeBase


async def _get_user_columns(db_engine: AsyncEngine) -> list[dict]:
    """Return column info for the users table in a database-agnostic way.

    Works with both SQLite (PRAGMA) and PostgreSQL (information_schema).

    Args:
        db_engine: The async engine to query.

    Returns:
        list[dict]: Column info dicts with keys: name, type, nullable
    """
    async with db_engine.connect() as conn:
        # Detect dialect from the engine URL
        dialect_name = db_engine.dialect.name.lower()

        if dialect_name == "sqlite":
            result = await conn.execute(text("PRAGMA table_info(users)"))
            rows = result.fetchall()
            columns = []
            for row in rows:
                columns.append(
                    {
                        "name": row[1],
                        "type": row[2],
                        "nullable": row[3] == 0,  # notnull=0 means nullable
                    }
                )
            return columns
        else:
            # PostgreSQL and others: use information_schema
            result = await conn.execute(
                text(
                    "SELECT column_name, data_type, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_name = 'users'"
                )
            )
            rows = result.fetchall()
            columns = []
            for row in rows:
                columns.append(
                    {
                        "name": row[0],
                        "type": row[1],
                        "nullable": row[2] == "YES",
                    }
                )
            return columns

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_migration_file_exists() -> None:
    """Test that the deleted_at migration file exists."""
    versions_dir = PROJECT_ROOT / "alembic" / "versions"
    migration_files = list(versions_dir.glob("*.py"))
    deleted_at_files = [f for f in migration_files if "deleted_at" in f.name.lower()]
    assert len(deleted_at_files) >= 1, "A migration file for deleted_at should exist"


def test_migration_adds_deleted_at_column_to_users_table() -> None:
    """AC-001: Database migration adds `deleted_at` column to `users` table.

    Verifies that the migration file contains the correct SQL to add the
    deleted_at column to the users table via op.add_column.
    """
    versions_dir = PROJECT_ROOT / "alembic" / "versions"
    migration_files = list(versions_dir.glob("*.py"))
    deleted_at_files = [f for f in migration_files if "deleted_at" in f.name.lower()]
    assert len(deleted_at_files) >= 1, "deleted_at migration should exist"

    content = deleted_at_files[0].read_text()
    assert "deleted_at" in content, "Migration should reference deleted_at"
    assert "add_column" in content, "Migration should add a column"
    assert "users" in content, "Migration should target users table"


def test_migration_deleted_at_is_nullable() -> None:
    """AC-002: `deleted_at` column is nullable.

    Verifies that the migration creates the column with nullable=True.
    """
    versions_dir = PROJECT_ROOT / "alembic" / "versions"
    migration_files = list(versions_dir.glob("*.py"))
    deleted_at_files = [f for f in migration_files if "deleted_at" in f.name.lower()]
    content = deleted_at_files[0].read_text()
    assert "nullable=True" in content, "deleted_at column should be nullable"


def test_migration_deleted_at_is_datetime_type() -> None:
    """AC-003: `deleted_at` column is of timestamp (DateTime) type.

    Verifies that the migration creates the column as a DateTime type,
    not a boolean or other type.
    """
    versions_dir = PROJECT_ROOT / "alembic" / "versions"
    migration_files = list(versions_dir.glob("*.py"))
    deleted_at_files = [f for f in migration_files if "deleted_at" in f.name.lower()]
    content = deleted_at_files[0].read_text()
    assert "DateTime" in content, "deleted_at column should be of DateTime type"
    assert (
        "Boolean" not in content
        or "deleted_at" not in content.split("Boolean")[0].split("\n")[-1]
    ), "deleted_at should not be Boolean type"


@pytest.mark.asyncio
async def test_migration_applied_creates_column(db_engine: AsyncEngine) -> None:
    """Test that applying the migration creates the deleted_at column.

    Uses SQLAlchemy's create_all to build the schema from the model
    (which includes deleted_at) and verifies the column exists.
    """
    async with db_engine.begin() as conn:
        await conn.run_sync(DeclarativeBase.metadata.create_all)

    columns = await _get_user_columns(db_engine)
    column_names = {c["name"] for c in columns}
    assert "deleted_at" in column_names, "deleted_at column should exist in users table"


@pytest.mark.asyncio
async def test_deleted_at_column_nullable_in_schema(db_engine: AsyncEngine) -> None:
    """Test that deleted_at column allows NULL values in the schema.

    Verifies the column's nullable flag is True in the database schema.
    """
    async with db_engine.begin() as conn:
        await conn.run_sync(DeclarativeBase.metadata.create_all)

    columns = await _get_user_columns(db_engine)
    deleted_at = next((c for c in columns if c["name"] == "deleted_at"), None)
    assert deleted_at is not None, "deleted_at column should exist"
    assert deleted_at["nullable"], "deleted_at column should be nullable"


@pytest.mark.asyncio
async def test_deleted_at_column_type_in_schema(db_engine: AsyncEngine) -> None:
    """Test that deleted_at column is of DateTime type in the schema.

    Verifies the column's type is DateTime in the database schema.
    """
    async with db_engine.begin() as conn:
        await conn.run_sync(DeclarativeBase.metadata.create_all)

    columns = await _get_user_columns(db_engine)
    deleted_at = next((c for c in columns if c["name"] == "deleted_at"), None)
    assert deleted_at is not None, "deleted_at column should exist"
    column_type = deleted_at["type"].lower()
    assert "datetime" in column_type or "timestamp" in column_type or "date" in column_type, (
        f"deleted_at column should be DateTime/Date type, got {column_type}"
    )


@pytest.mark.asyncio
async def test_model_has_deleted_at_field() -> None:
    """Test that the User model includes a deleted_at field.

    Verifies the ORM model has the deleted_at column defined.
    """
    from src.users.models import User

    assert hasattr(User, "deleted_at"), "User model should have a deleted_at attribute"


@pytest.mark.asyncio
async def test_migration_has_correct_down_revision() -> None:
    """Test that the migration chains correctly from the latest migration.

    Verifies the migration's down_revision points to the most recent
    migration (3df3d0abd941).
    """
    versions_dir = PROJECT_ROOT / "alembic" / "versions"
    migration_files = list(versions_dir.glob("*.py"))
    deleted_at_files = [f for f in migration_files if "deleted_at" in f.name.lower()]
    content = deleted_at_files[0].read_text()
    assert "down_revision" in content, "Migration should have down_revision"
    assert "3df3d0abd941" in content, "Migration should chain from 3df3d0abd941"


def test_migration_chain_is_valid() -> None:
    """Test that the migration chain is valid.

    Verifies all migration files can be parsed and their revision
    references are consistent.
    """
    versions_dir = PROJECT_ROOT / "alembic" / "versions"
    migration_files = list(versions_dir.glob("*.py"))

    # Build a map of revision -> file
    revisions: dict[str, Path] = {}
    for f in migration_files:
        content = f.read_text()
        # Extract revision ID
        for line in content.split("\n"):
            if line.startswith("revision:"):
                rev = line.split("=")[1].strip().strip("'\"")
                revisions[rev] = f
                break

    # Verify all down_revision references point to existing migrations
    for f in migration_files:
        content = f.read_text()
        for line in content.split("\n"):
            if line.startswith("down_revision:"):
                rev = line.split("=")[1].strip().strip("'\"")
                if rev != "None":
                    assert rev in revisions, (
                        f"Migration {f.name} references "
                        f"down_revision {rev} which does not exist"
                    )
