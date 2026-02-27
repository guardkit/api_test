"""Tests for Alembic configuration."""

from __future__ import annotations

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


def test_alembic_env_uses_settings_database_url() -> None:
    """Test that alembic/env.py uses settings.database_url."""
    project_root = Path(__file__).resolve().parents[1]
    env_py = project_root / "alembic" / "env.py"
    content = env_py.read_text()
    assert "settings.database_url" in content, "env.py should use settings.database_url"


def test_alembic_env_async_migration() -> None:
    """Test that alembic/env.py has async migration runner."""
    project_root = Path(__file__).resolve().parents[1]
    env_py = project_root / "alembic" / "env.py"
    content = env_py.read_text()
    assert "run_async_migrations" in content, "env.py should have async migration runner"
    assert "AsyncConnection" in content, "env.py should import AsyncConnection"
    assert "create_async_engine" in content, "env.py should use create_async_engine"
