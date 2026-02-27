"""Tests for Alembic configuration."""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

import pytest


def test_alembic_ini_exists() -> None:
    """Test that alembic.ini exists at project root."""
    project_root = Path(__file__).resolve().parents[1]
    alembic_ini = project_root / "alembic.ini"
    assert alembic_ini.exists(), "alembic.ini should exist at project root"


def test_alembic_directory_exists() -> None:
    """Test that alembic directory exists."""
    project_root = Path(__file__).resolve().parents[1]
    alembic_dir = project_root / "alembic"
    assert alembic_dir.is_dir(), "alembic directory should exist"


def test_alembic_env_py_exists() -> None:
    """Test that alembic/env.py exists."""
    project_root = Path(__file__).resolve().parents[1]
    env_py = project_root / "alembic" / "env.py"
    assert env_py.exists(), "alembic/env.py should exist"


def test_alembic_script_py_mako_exists() -> None:
    """Test that alembic/script.py.mako exists."""
    project_root = Path(__file__).resolve().parents[1]
    script_py_mako = project_root / "alembic" / "script.py.mako"
    assert script_py_mako.exists(), "alembic/script.py.mako should exist"


def test_alembic_versions_directory_exists() -> None:
    """Test that alembic/versions directory exists."""
    project_root = Path(__file__).resolve().parents[1]
    versions_dir = project_root / "alembic" / "versions"
    assert versions_dir.is_dir(), "alembic/versions should be a directory"


def test_alembic_env_imports_base_metadata() -> None:
    """Test that alembic/env.py imports DeclarativeBase.metadata."""
    project_root = Path(__file__).resolve().parents[1]
    env_py = project_root / "alembic" / "env.py"
    content = env_py.read_text()
    assert "DeclarativeBase.metadata" in content, "env.py should import DeclarativeBase.metadata"


def test_alembic_env_uses_database_url() -> None:
    """Test that alembic/env.py uses DATABASE_URL."""
    project_root = Path(__file__).resolve().parents[1]
    env_py = project_root / "alembic" / "env.py"
    content = env_py.read_text()
    assert "DATABASE_URL" in content, "env.py should use DATABASE_URL environment variable"


def test_alembic_env_async_migration() -> None:
    """Test that alembic/env.py has async migration runner."""
    project_root = Path(__file__).resolve().parents[1]
    env_py = project_root / "alembic" / "env.py"
    content = env_py.read_text()
    assert "run_async_migrations" in content, "env.py should have async migration runner"
    assert "AsyncConnection" in content, "env.py should import AsyncConnection"
    assert "create_async_engine" in content, "env.py should use create_async_engine"


def test_migration_file_exists() -> None:
    """Test that the users table migration file exists."""
    project_root = Path(__file__).resolve().parents[1]
    migration_file = project_root / "alembic" / "versions"
    migration_files = list(migration_file.glob("*.py"))
    assert len(migration_files) > 0, "At least one migration file should exist"


def test_users_table_migration_contains_columns() -> None:
    """Test that the users table migration contains all required columns."""
    project_root = Path(__file__).resolve().parents[1]
    migration_file = project_root / "alembic" / "versions"
    migration_files = list(migration_file.glob("*.py"))

    # Find the users table migration
    users_migration = None
    for f in migration_files:
        if "users" in f.name.lower() or "user" in f.name.lower():
            users_migration = f
            break

    assert users_migration is not None, "Users table migration should exist"
    content = users_migration.read_text()

    # Check for required columns
    assert "email" in content, "Migration should contain email column"
    assert "full_name" in content, "Migration should contain full_name column"
    assert "is_active" in content, "Migration should contain is_active column"
    assert "created_at" in content, "Migration should contain created_at column"
    assert "updated_at" in content, "Migration should contain updated_at column"


def test_users_table_migration_has_unique_constraint() -> None:
    """Test that the users table migration has a unique constraint on email."""
    project_root = Path(__file__).resolve().parents[1]
    migration_file = project_root / "alembic" / "versions"
    migration_files = list(migration_file.glob("*.py"))

    users_migration = None
    for f in migration_files:
        if "users" in f.name.lower():
            users_migration = f
            break

    assert users_migration is not None, "Users table migration should exist"
    content = users_migration.read_text()

    # Check for unique constraint
    assert "unique" in content.lower(), "Migration should contain unique constraint"


def test_users_table_migration_has_index() -> None:
    """Test that the users table migration has an index on email."""
    project_root = Path(__file__).resolve().parents[1]
    migration_file = project_root / "alembic" / "versions"
    migration_files = list(migration_file.glob("*.py"))

    users_migration = None
    for f in migration_files:
        if "users" in f.name.lower():
            users_migration = f
            break

    assert users_migration is not None, "Users table migration should exist"
    content = users_migration.read_text()

    # Check for index
    assert "index" in content.lower(), "Migration should contain index"


def test_alembic_upgrade_and_downgrade() -> None:
    """Test that migration applies and rolls back cleanly using subprocess."""
    project_root = Path(__file__).resolve().parents[1]

    # Use SQLite for testing
    test_db_path = project_root / "test_migration.db"
    test_db_url = f"sqlite+aiosqlite:///{test_db_path}"

    # Set environment variable
    env = os.environ.copy()
    env["DATABASE_URL"] = test_db_url

    try:
        # Run upgrade using subprocess
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Upgrade failed: {result.stderr}"

        # Verify the database has the users table using SQLAlchemy
        import asyncio

        async def verify_table():
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import create_async_engine

            engine = create_async_engine(test_db_url)
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name='users';
                    """
                    )
                )
                table = result.scalar()
                assert table == "users", "users table should exist after upgrade"

            await engine.dispose()

        asyncio.run(verify_table())

        # Run downgrade using subprocess
        result = subprocess.run(
            ["alembic", "downgrade", "base"],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Downgrade failed: {result.stderr}"

        # Verify the database no longer has the users table
        async def verify_no_table():
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import create_async_engine

            engine = create_async_engine(test_db_url)
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name='users';
                    """
                    )
                )
                table = result.scalar()
                assert table is None, "users table should not exist after downgrade"

            await engine.dispose()

        asyncio.run(verify_no_table())

    finally:
        # Cleanup
        if test_db_path.exists():
            test_db_path.unlink()
