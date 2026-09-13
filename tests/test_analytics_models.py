"""Tests for the user-creation analytics models and schemas.

Covers TASK-BD8F-001:

- AC-001: the Pydantic schema ``UserCreationStats`` defines the response shape
  for user-creation analytics (per-day counts, ordered oldest first).
- AC-002: the SQLAlchemy model side (``UserAnalytics`` plus the extension of the
  existing ``User`` model) supports creation timestamp queries, and those
  queries are built in this feature's crud.py, as R-OV-1 requires.
- AC-004: the analytics API carries type annotations on arguments and returns.

The model tests use their own in-memory SQLite engine, mirroring
``tests/users/test_models.py``, so a test never depends on a shared database.
"""

from __future__ import annotations

import ast
import inspect
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError
from sqlalchemy import Select, Table, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.base import DeclarativeBase
from src.users import crud
from src.users.crud import (
    users_created_between_statement,
    users_created_per_day_statement,
)
from src.users.models import User, UserAnalytics, creation_day_expression
from src.users.schemas import (
    DEFAULT_USER_CREATION_WINDOW_DAYS,
    UserCreationDayCount,
    UserCreationStats,
)

# A fixed week, so no test depends on the wall clock.
WINDOW_START = date(2026, 7, 2)


def timestamp_on(day: date, hour: int = 12) -> datetime:
    """Return a naive UTC timestamp on ``day``.

    Naive matches the ``created_at`` column type declared by the User model,
    which carries no timezone; comparing against an aware datetime is what made
    PostgreSQL refuse the count-today query once already.

    Args:
        day: The calendar day to place the timestamp on.
        hour: Hour of day, defaulting to midday.

    Returns:
        datetime: The naive timestamp.
    """
    return datetime(day.year, day.month, day.day, hour)


class TestUserCreationStatsSchema:
    """AC-001: ``UserCreationStats`` defines the response shape."""

    def test_schema_exposes_the_response_fields(self) -> None:
        """The response is a list of per-day entries plus a total."""
        stats = UserCreationStats(
            days=[UserCreationDayCount(date=WINDOW_START, count=3)]
        )

        assert set(stats.model_dump()) == {"days", "total"}
        assert stats.days[0].date == WINDOW_START
        assert stats.days[0].count == 3
        assert stats.total == 3

    def test_schema_serialises_days_as_iso_dates(self) -> None:
        """A day entry renders as an ISO date with its count."""
        stats = UserCreationStats(
            days=[UserCreationDayCount(date=WINDOW_START, count=0)]
        )

        payload = stats.model_dump(mode="json")

        assert payload == {"days": [{"date": "2026-07-02", "count": 0}], "total": 0}

    def test_days_are_ordered_oldest_first_whatever_they_arrive_as(self) -> None:
        """The ordering contract of the endpoint holds by construction."""
        days = [
            UserCreationDayCount(date=date(2026, 7, 8), count=1),
            UserCreationDayCount(date=date(2026, 7, 2), count=2),
            UserCreationDayCount(date=date(2026, 7, 5), count=3),
        ]

        stats = UserCreationStats(days=days)

        assert [entry.date for entry in stats.days] == [
            date(2026, 7, 2),
            date(2026, 7, 5),
            date(2026, 7, 8),
        ]

    def test_total_is_the_sum_of_the_daily_counts(self) -> None:
        """``total`` is derived, never supplied."""
        stats = UserCreationStats(
            days=[
                UserCreationDayCount(date=WINDOW_START, count=2),
                UserCreationDayCount(date=date(2026, 7, 3), count=5),
            ]
        )

        assert stats.total == 7

    def test_negative_counts_are_refused(self) -> None:
        """A day cannot have created a negative number of users."""
        with pytest.raises(ValidationError):
            UserCreationStats(days=[UserCreationDayCount(date=WINDOW_START, count=-1)])

    def test_the_same_day_cannot_appear_twice(self) -> None:
        """Per-day rows are unique; duplicates mean the query grouped wrongly."""
        with pytest.raises(ValidationError):
            UserCreationStats(
                days=[
                    UserCreationDayCount(date=WINDOW_START, count=1),
                    UserCreationDayCount(date=WINDOW_START, count=2),
                ]
            )

    def test_window_covers_seven_days(self) -> None:
        """The feature asks for the last seven days."""
        assert DEFAULT_USER_CREATION_WINDOW_DAYS == 7

    def test_zero_filled_window_yields_every_day_oldest_first(self) -> None:
        """A week with no creations still answers with all seven days."""
        stats = UserCreationStats.zero_filled_window(WINDOW_START)

        assert len(stats.days) == 7
        assert [entry.date for entry in stats.days] == [
            date(2026, 7, day) for day in range(2, 9)
        ]
        assert all(entry.count == 0 for entry in stats.days)
        assert stats.total == 0

    def test_zero_filled_window_needs_at_least_one_day(self) -> None:
        """An empty window is a mistake, said plainly."""
        with pytest.raises(ValueError, match="at least one"):
            UserCreationStats.zero_filled_window(WINDOW_START, window_days=0)

    def test_a_day_entry_carries_a_documented_example(self) -> None:
        """The schema documents an example, as the other schemas do."""
        extra = UserCreationDayCount.model_config.get("json_schema_extra")

        assert isinstance(extra, dict)
        assert "examples" in extra


class TestCreationTimestampQuerySupport:
    """AC-002: creation timestamp queries are supported.

    The conditions and day arithmetic belong to the model layer, the statements
    that read the database belong to the feature's crud.py — which is where
    these tests reach them from.
    """

    def test_created_at_is_indexed(self) -> None:
        """Creation timestamp queries are served by an index."""
        assert User.__table__.c.created_at.index is True
        indexed = {index.name for index in cast(Table, User.__table__).indexes}
        assert "ix_users_created_at" in indexed

    def test_creation_day_reads_the_calendar_day_of_a_user(self) -> None:
        """The Python side of the hybrid yields the creation calendar day."""
        naive = User(email="naive@example.com", created_at=timestamp_on(WINDOW_START))
        aware = User(
            email="aware@example.com",
            created_at=timestamp_on(WINDOW_START).replace(
                hour=23, minute=59, tzinfo=UTC
            ),
        )

        assert naive.creation_day == WINDOW_START
        assert UserAnalytics.creation_day(naive) == WINDOW_START
        assert aware.creation_day == WINDOW_START

    def test_creation_day_expression_groups_by_the_creation_column(self) -> None:
        """The SQL side of the hybrid names the creation timestamp column."""
        statement = users_created_per_day_statement(WINDOW_START, WINDOW_START)

        sql = str(statement)
        assert "created_at" in sql
        assert "GROUP BY" in sql

    def test_the_between_window_query_selects_the_creation_timestamp_range(
        self,
    ) -> None:
        """A window query filters the timestamp range and skips soft deletions."""
        statement = users_created_between_statement(
            timestamp_on(WINDOW_START), timestamp_on(date(2026, 7, 9))
        )

        assert isinstance(statement, Select)
        sql = str(statement)
        assert "users.created_at >= :" in sql
        assert "users.created_at < :" in sql
        assert "deleted_at IS NULL" in sql

    def test_the_between_window_query_can_keep_soft_deleted_users(self) -> None:
        """History queries may name deleted rows explicitly."""
        statement = users_created_between_statement(
            timestamp_on(WINDOW_START),
            timestamp_on(date(2026, 7, 9)),
            include_deleted=True,
        )

        assert "deleted_at IS NULL" not in str(statement)

    def test_the_between_window_query_refuses_a_reversed_window(self) -> None:
        """A reversed range is a programming error, said plainly."""
        with pytest.raises(ValueError, match="precedes"):
            users_created_between_statement(
                timestamp_on(date(2026, 7, 9)), timestamp_on(WINDOW_START)
            )

    def test_the_per_day_count_query_refuses_a_reversed_window(self) -> None:
        """The per-day count query says so too."""
        with pytest.raises(ValueError, match="precedes"):
            users_created_per_day_statement(date(2026, 7, 9), WINDOW_START)

    def test_creation_day_expression_names_the_creation_column(self) -> None:
        """The shared SQL expression reads the creation timestamp column."""
        sql = str(creation_day_expression())

        assert "date(users.created_at)" in sql

    def test_creation_day_hybrid_is_the_same_expression_in_sql(self) -> None:
        """Read through SQL, the hybrid spells the day the same way."""
        assert "date(users.created_at)" in str(select(User.creation_day))

    def test_a_value_that_is_not_shaped_like_a_day_is_refused(self) -> None:
        """A value no database hands back is named, not coerced."""
        with pytest.raises(TypeError, match="creation day"):
            UserAnalytics.daily_counts([(None, 1)])

    def test_daily_counts_normalises_and_orders_rows(self) -> None:
        """Dialect-specific day values become dates, oldest first."""
        rows = [
            ("2026-07-05", 4),
            (datetime(2026, 7, 2, 0, 0), 1),
            (date(2026, 7, 3), 2),
        ]

        assert UserAnalytics.daily_counts(rows) == [
            (date(2026, 7, 2), 1),
            (date(2026, 7, 3), 2),
            (date(2026, 7, 5), 4),
        ]

    def test_daily_counts_refuses_a_value_that_is_not_a_day(self) -> None:
        """A row that is not a day is reported, not guessed at."""
        with pytest.raises(ValueError, match="creation day"):
            UserAnalytics.daily_counts([("not-a-day", 1)])

    def test_daily_counts_refuses_a_row_that_is_not_a_pair(self) -> None:
        """A malformed row shape is reported, not guessed at."""
        with pytest.raises(ValueError, match="day and a count"):
            UserAnalytics.daily_counts([("2026-07-02",)])


class TestCreationTimestampQueriesAgainstADatabase:
    """AC-002: the queries actually run."""

    @pytest.fixture(autouse=True)
    async def setup_database(self) -> None:
        """Set up an in-memory SQLite database holding users."""
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(DeclarativeBase.metadata.create_all)
        self.async_session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @pytest.fixture
    async def async_session(self) -> AsyncIterator[AsyncSession]:
        """Create an async session for testing."""
        async with self.async_session_factory() as session:
            yield session

    async def _add_user(
        self, session: AsyncSession, email: str, created_at: datetime
    ) -> User:
        """Persist a user whose creation timestamp is ``created_at``."""
        user = User(email=email, created_at=created_at)
        session.add(user)
        await session.commit()
        return user

    async def test_users_are_counted_per_creation_day(
        self, async_session: AsyncSession
    ) -> None:
        """Each creation day carries the number of users created on it."""
        await self._add_user(async_session, "a@example.com", timestamp_on(WINDOW_START))
        await self._add_user(
            async_session, "b@example.com", timestamp_on(WINDOW_START, hour=23)
        )
        await self._add_user(
            async_session, "c@example.com", timestamp_on(date(2026, 7, 4))
        )
        await self._add_user(
            async_session, "outside@example.com", timestamp_on(date(2026, 7, 20))
        )

        rows = await async_session.execute(
            users_created_per_day_statement(WINDOW_START, date(2026, 7, 8))
        )

        assert UserAnalytics.daily_counts(rows.all()) == [
            (WINDOW_START, 2),
            (date(2026, 7, 4), 1),
        ]

    async def test_soft_deleted_users_keep_their_creation_day_out(
        self, async_session: AsyncSession
    ) -> None:
        """Deleted users are not counted as creations, as elsewhere."""
        kept = await self._add_user(
            async_session, "kept@example.com", timestamp_on(WINDOW_START)
        )
        removed = await self._add_user(
            async_session, "removed@example.com", timestamp_on(WINDOW_START)
        )
        removed.deleted_at = datetime(2026, 7, 6)
        await async_session.commit()

        rows = await async_session.execute(
            users_created_per_day_statement(WINDOW_START, date(2026, 7, 8))
        )

        assert UserAnalytics.daily_counts(rows.all()) == [(WINDOW_START, 1)]
        assert kept.email == "kept@example.com"

    async def test_a_window_without_creations_answers_with_zero_filled_days(
        self, async_session: AsyncSession
    ) -> None:
        """An empty week answers with seven zero days, oldest first."""
        await self._add_user(
            async_session, "long-ago@example.com", timestamp_on(date(2020, 1, 1))
        )

        rows = await async_session.execute(
            users_created_per_day_statement(WINDOW_START, date(2026, 7, 8))
        )

        stats = UserCreationStats.zero_filled_window(WINDOW_START)
        assert UserAnalytics.daily_counts(rows.all()) == []
        assert len(stats.days) == 7
        assert stats.total == 0

    async def test_the_between_window_query_finds_users_by_creation_timestamp(
        self, async_session: AsyncSession
    ) -> None:
        """The range query returns exactly the users created inside it."""
        inside = await self._add_user(
            async_session, "inside@example.com", timestamp_on(date(2026, 7, 5))
        )
        await self._add_user(
            async_session, "before@example.com", timestamp_on(date(2026, 7, 1))
        )
        await self._add_user(
            async_session, "after@example.com", timestamp_on(date(2026, 7, 9))
        )

        result = await async_session.execute(
            users_created_between_statement(
                timestamp_on(WINDOW_START), timestamp_on(date(2026, 7, 9))
            )
        )

        assert [user.email for user in result.scalars()] == [inside.email]


class TestAnalyticsApiIsAnnotated:
    """AC-004: arguments and return values carry annotations."""

    def test_analytics_callables_are_fully_annotated(self) -> None:
        """Every new analytics callable says what it takes and returns."""
        callables: list[Any] = [
            crud.users_created_between_statement,
            crud.users_created_per_day_statement,
            User.created_in_window,
            UserAnalytics.creation_day,
            UserAnalytics.daily_count_window,
            UserAnalytics.daily_counts,
            UserCreationStats.zero_filled_window,
            timestamp_on,
        ]

        for target in callables:
            signature = inspect.signature(target)
            assert signature.return_annotation is not inspect.Signature.empty, target
            for name, parameter in signature.parameters.items():
                if name in ("self", "cls"):
                    continue
                assert parameter.annotation is not inspect.Parameter.empty, (
                    target,
                    name,
                )


QUERY_BUILDING_NAMES: frozenset[str] = frozenset(
    {"select", "insert", "update", "delete"}
)
"""The SQLAlchemy names whose call sites the architecture rule watches."""


def query_call_lines(path: Path) -> list[int]:
    """Lines where ``path`` builds a database query inside a function body.

    Reads the syntax tree, not the text, so a query quoted in a docstring stays
    invisible — the same reading docs/architecture-rules.yaml asks of the
    conformance checker for R-OV-1.

    Args:
        path: The source file to read.

    Returns:
        list[int]: The line numbers of the query call sites, smallest first.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    query_names = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and (node.module or "").split(".")[0] == "sqlalchemy"
        for alias in node.names
        if alias.name in QUERY_BUILDING_NAMES
    }
    if not query_names:
        return []

    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for call in ast.walk(node):
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id in query_names
            ):
                lines.append(call.lineno)
    return sorted(set(lines))


class TestQueriesLiveInTheFeatureCrudFile:
    """R-OV-1: database queries live in crud.py, not in models.py or router.py."""

    def test_the_model_file_builds_no_database_queries(self) -> None:
        """The analytics helpers stay out of the query business."""
        models_file = Path(crud.__file__).with_name("models.py")

        assert query_call_lines(models_file) == []

    def test_the_model_router_builds_no_database_queries(self) -> None:
        """The feature's router holds no query of its own."""
        router_file = Path(crud.__file__).with_name("router.py")

        assert query_call_lines(router_file) == []

    def test_the_creation_timestamp_queries_are_built_in_crud(self) -> None:
        """Both creation-window queries have their home in this crud file."""
        assert query_call_lines(Path(crud.__file__))
