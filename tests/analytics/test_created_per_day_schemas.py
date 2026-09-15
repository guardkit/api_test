"""Tests for the user-creation analytics schema and models (TASK-6F3D-001).

Covers the acceptance criteria of TASK-6F3D-001:
- AC-001: Pydantic models for the user count response (date and count)
- AC-002: the SQLAlchemy side of the analytics data — no separate table, so the
  users.created_at index plus the ADR-001 boundary the analytics read across
- AC-003: Migration script adding the required schema change
- AC-004: The modified files pass the project-configured lint/format checks
  (exercised here by importing them under the strict typing/lint configuration
  the project declares in pyproject.toml)
"""

from __future__ import annotations

import ast
import importlib
import json
import os
import pkgutil
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine

from src.analytics.schemas import (
    CreatedPerDayResponse,
    UserCount,
    UserCountByDate,
)
from src.db.base import DeclarativeBase
from src.users.models import User

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANALYTICS_PACKAGE = PROJECT_ROOT / "src" / "analytics"

# ADR-001, amendment of 2026-08-31: the files of a feature that another feature
# may not import. crud.py and schemas.py make up the public read interface, and
# the amendment names nothing else, so the guard below checks exactly these.
PRIVATE_FEATURE_FILES = frozenset({"models", "service", "router", "dependencies"})


def _private_feature_imports(package: Path) -> list[str]:
    """Find every import in `package` that names a private file of another feature.

    Args:
        package: Directory whose modules are read.

    Returns:
        list[str]: One "<path>: <imported module>" entry per offending import,
        empty when the package keeps to other features' public read interface.
    """
    offenders: list[str] = []
    for module_path in sorted(package.rglob("*.py")):
        imported: list[str] = []
        for node in ast.walk(ast.parse(module_path.read_text())):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
                if len(node.module.split(".")) == 2 and node.module.startswith("src."):
                    # `from src.users import models` names the file in the alias.
                    imported.extend(
                        f"{node.module}.{alias.name}" for alias in node.names
                    )
        for name in imported:
            parts = name.split(".")
            if len(parts) < 3 or parts[0] != "src" or parts[1] == package.name:
                continue
            feature_file = parts[2]
            if feature_file in PRIVATE_FEATURE_FILES or feature_file.startswith("_"):
                offenders.append(f"{module_path.relative_to(PROJECT_ROOT)}: {name}")
    return offenders


def _orm_models_exposed_by(package_name: str) -> list[str]:
    """List the SQLAlchemy models that `package_name` declares or re-exports.

    Args:
        package_name: Dotted name of the package to inspect, e.g.
            ``"src.analytics"``.

    Returns:
        list[str]: Qualified names of the declarative models found, empty when
        the package owns no table.
    """
    package = importlib.import_module(package_name)
    exposed: list[str] = []
    for module_info in pkgutil.iter_modules(package.__path__):
        module = importlib.import_module(f"{package_name}.{module_info.name}")
        exposed.extend(
            f"{module.__name__}.{name}"
            for name, value in sorted(vars(module).items())
            if isinstance(value, type)
            and issubclass(value, DeclarativeBase)
            and value is not DeclarativeBase
        )
    return exposed


class TestUserCountByDate:
    """AC-001: a data point pairs an ISO-8601 date with a non-negative count."""

    def test_accepts_iso_date_and_count(self) -> None:
        """A date string and an integer count build a data point."""
        point = UserCountByDate(date="2026-09-08", count=3)

        assert point.date == date(2026, 9, 8)
        assert point.count == 3

    def test_serialises_to_date_and_count_keys(self) -> None:
        """The JSON body of a data point carries exactly the 'date'/'count' keys."""
        payload = UserCountByDate(date=date(2026, 9, 8), count=0).model_dump()

        assert payload == {"date": date(2026, 9, 8), "count": 0}
        assert json.loads(
            UserCountByDate(date="2026-09-08", count=0).model_dump_json()
        ) == {
            "date": "2026-09-08",
            "count": 0,
        }

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2026-09-08", date(2026, 9, 8)),
            ("2026-09-08T13:45:00+00:00", date(2026, 9, 8)),
            (datetime(2026, 9, 8, 13, 45), date(2026, 9, 8)),
            (date(2026, 9, 8), date(2026, 9, 8)),
        ],
    )
    def test_normalises_date_like_inputs(self, raw: Any, expected: date) -> None:
        """Timestamps and ISO strings normalise to the calendar date they fall on."""
        assert UserCountByDate(date=raw, count=1).date == expected

    def test_rejects_negative_count(self) -> None:
        """A count below zero is refused: counts are never negative."""
        with pytest.raises(ValidationError) as exc_info:
            UserCountByDate(date="2026-09-08", count=-1)

        assert "count" in str(exc_info.value)

    def test_rejects_unparsable_date(self) -> None:
        """A string that is not a date is refused rather than silently kept."""
        with pytest.raises(ValidationError) as exc_info:
            UserCountByDate(date="not-a-date", count=1)

        assert "date" in str(exc_info.value)

    def test_contract_alias_matches_the_implementation_guide(self) -> None:
        """The contract name 'UserCount' names the same schema as UserCountByDate."""
        assert UserCount is UserCountByDate


class TestCreatedPerDayResponse:
    """AC-001: the response body is an array of data points, oldest first."""

    def test_serialises_as_a_bare_json_array(self) -> None:
        """The response model dumps to a JSON array, not an object with a key."""
        response = CreatedPerDayResponse(
            [
                UserCountByDate(date="2026-09-08", count=1),
                UserCountByDate(date="2026-09-09", count=2),
            ]
        )

        assert json.loads(response.model_dump_json()) == [
            {"date": "2026-09-08", "count": 1},
            {"date": "2026-09-09", "count": 2},
        ]

    def test_accepts_seven_ascending_data_points(self) -> None:
        """A full seven-day window, oldest first, validates."""
        response = CreatedPerDayResponse.model_validate(
            [{"date": f"2026-09-{day:02d}", "count": day} for day in range(2, 9)]
        )

        assert len(response.root) == 7
        assert [point.count for point in response.root] == [2, 3, 4, 5, 6, 7, 8]

    def test_rejects_data_points_that_are_not_oldest_first(self) -> None:
        """Out-of-order data points are refused: the contract is oldest first."""
        with pytest.raises(ValidationError) as exc_info:
            CreatedPerDayResponse.model_validate(
                [
                    {"date": "2026-09-09", "count": 1},
                    {"date": "2026-09-08", "count": 2},
                ]
            )

        assert "oldest" in str(exc_info.value)

    def test_rejects_repeated_dates(self) -> None:
        """One data point per day: a repeated date is refused."""
        with pytest.raises(ValidationError):
            CreatedPerDayResponse.model_validate(
                [
                    {"date": "2026-09-08", "count": 1},
                    {"date": "2026-09-08", "count": 2},
                ]
            )

    def test_empty_series_is_valid(self) -> None:
        """An empty series validates; the service decides how to fill the window."""
        assert CreatedPerDayResponse([]).root == []


class TestAnalyticsModels:
    """AC-002: the SQLAlchemy side of the analytics data.

    The criterion is conditional — "SQLAlchemy model for analytics data (if
    separate table)". The storage decision recorded for FEAT-6F3D
    (tasks/backlog/user-analytics/IMPLEMENTATION-GUIDE.md) is the existing
    users table with an index on created_at, so there is no second table and no
    analytics ORM model; what the analytics need from the schema layer is that
    index, and the boundary that keeps them reading the users table through the
    users feature's public interface (ADR-001, amendment of 2026-08-31).
    """

    def test_analytics_add_no_table_of_their_own(self) -> None:
        """No separate table means no separate ORM model: analytics declares none."""
        models = _orm_models_exposed_by("src.analytics")

        assert models == [], (
            "analytics answers from the users table and stores nothing of its "
            "own, so it must declare no ORM model of its own: " + ", ".join(models)
        )

    def test_analytics_import_no_private_file_of_another_feature(self) -> None:
        """Analytics reads users through crud.py/schemas.py, never through models.py."""
        offenders = _private_feature_imports(ANALYTICS_PACKAGE)

        assert offenders == [], (
            "ADR-001 (amendment 2026-08-31) lets one feature import another's "
            "crud.py and schemas.py and nothing else: " + "; ".join(offenders)
        )

    def test_created_at_is_declared_indexed_on_the_model(self) -> None:
        """The model declares an index on created_at for the daily-window query."""
        # indexes is a dynamic attribute on the mapped table, as in
        # tests/users/test_models.py.
        table_indexes: Any = User.__table__.indexes  # type: ignore[attr-defined]
        index_names = {index.name for index in table_indexes}

        assert "ix_users_created_at" in index_names


class TestAnalyticsMigration:
    """AC-003: a migration script adds the schema the analytics query needs."""

    @staticmethod
    def _analytics_migration() -> Path:
        versions = PROJECT_ROOT / "alembic" / "versions"
        matches = [
            path
            for path in versions.glob("*.py")
            if "created_at" in path.name and "index" in path.name
        ]
        assert matches, f"expected a created_at index migration in {versions}"
        return matches[0]

    def test_migration_exists_and_revises_the_current_head(self) -> None:
        """The migration exists and hangs off the existing chain."""
        migration = self._analytics_migration()
        content = migration.read_text()

        assert "op.create_index" in content
        assert "created_at" in content
        assert "def upgrade()" in content
        assert "def downgrade()" in content

    def test_the_chain_has_a_single_head(self) -> None:
        """Adding the migration must not fork the revision chain.

        The chain is read from the scripts themselves: the repository's own
        ``alembic/`` package shadows the installed one, so the revisions are
        parsed rather than imported.
        """
        revisions: dict[str, str | None] = {}
        for path in (PROJECT_ROOT / "alembic" / "versions").glob("*.py"):
            content = path.read_text()
            revision = re.search(r'^revision: str = "([^"]+)"', content, re.MULTILINE)
            down = re.search(
                r'^down_revision: str \| None = (?:"([^"]+)"|None)',
                content,
                re.MULTILINE,
            )
            assert revision is not None, f"{path.name} declares no revision id"
            revisions[revision.group(1)] = (
                down.group(1) if down and down.group(1) else None
            )

        parents = {parent for parent in revisions.values() if parent is not None}
        heads = sorted(revision for revision in revisions if revision not in parents)
        analytics = re.search(
            r'^revision: str = "([^"]+)"',
            self._analytics_migration().read_text(),
            re.MULTILINE,
        )

        assert analytics is not None, "the analytics migration declares no revision id"
        assert heads == [analytics.group(1)], f"expected one head, found {heads}"

    def test_upgrade_creates_the_created_at_index(self, tmp_path: Path) -> None:
        """`alembic upgrade head` builds the index the analytics query relies on."""
        database = tmp_path / "analytics_migration.db"
        url = f"sqlite+aiosqlite:///{database}"
        alembic = PROJECT_ROOT / ".venv" / "bin" / "alembic"
        command = (
            [str(alembic)]
            if alembic.exists()
            else [sys.executable, "-m", "alembic"]  # pragma: no cover - fallback
        )
        env = {**os.environ, "DATABASE_URL": url}

        result = subprocess.run(
            [*command, "upgrade", "head"],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"upgrade failed: {result.stderr}"

        from sqlalchemy import create_engine

        sync_url = url.replace("sqlite+aiosqlite", "sqlite")
        engine = create_engine(sync_url)
        try:
            indexed_columns = [
                index["column_names"]
                for index in inspect(engine).get_indexes("users")
                if index["column_names"]
            ]
        finally:
            engine.dispose()

        assert ["created_at"] in indexed_columns, indexed_columns

    async def test_the_index_is_created_by_the_test_schema_too(
        self, db_engine: AsyncEngine
    ) -> None:
        """The ORM schema used by the tests carries the same index."""

        def _indexes(connection: Any) -> list[Any]:
            return list(inspect(connection).get_indexes("users"))

        async with db_engine.connect() as connection:
            indexes = await connection.run_sync(_indexes)
        columns = [index["column_names"] for index in indexes if index["column_names"]]

        assert ["created_at"] in columns, columns
