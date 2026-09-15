"""Tests for the analytics service layer (TASK-6F3D-004).

Covers the acceptance criteria of TASK-6F3D-004:

- AC-001: the service calculates the seven-day window it answers — the window
  bounds it asks the query for, and the series it lays over that window, are
  worked out here rather than trusted
- AC-002: every data point is formatted as an ISO-8601 calendar date, whether
  the row that produced it carried a ``date``, a ``datetime`` or a string
- AC-003: the files this task touches pass the project-configured lint/format
  checks (``ruff check`` and ``ruff format --check``, as pyproject.toml
  configures them) with zero errors

The service is graded without a database, as the task's implementation notes
ask: the window, the zero-filling and the formatting are exercised as plain
functions, and the retrieval step is stood in for by a fake that records the
bounds the service asked for. The HTTP behaviour of the endpoint that serves
this service is graded by ``tests/analytics/test_created_per_day_router.py``,
which reaches the same code through ``GET /users/created-per-day``.
"""

from __future__ import annotations

import ast
import inspect
import subprocess
import sys
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.analytics import router as analytics_router
from src.analytics import service as analytics_service
from src.analytics.schemas import CreatedPerDayResponse
from src.analytics.service import (
    DAILY_WINDOW_DAYS,
    build_daily_series,
    daily_window,
    format_data_point,
    get_users_created_per_day,
    iso_date,
    to_calendar_day,
    window_bounds,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: The files TASK-6F3D-004 writes: the new service layer, and the router that
#: now reaches the series through it instead of calling the query layer itself.
MODIFIED_FILES = ("src/analytics/service.py", "src/analytics/router.py")

#: Days in the window the endpoint promises, restated here so the service fails
#: these tests if it quietly widens or narrows the window.
WINDOW_DAYS = 7


def utc_today() -> date:
    """Today's UTC date, worked out here rather than imported.

    Importing ``src.analytics.service.utc_today`` would grade the
    implementation against itself, so the tests take the day the way the
    feature spec describes it: the current day in UTC.

    Returns:
        date: The current UTC calendar day.
    """
    return datetime.now(tz=UTC).date()


def at_midnight(day: date) -> datetime:
    """The first instant of a day, the form the query's bounds take.

    Args:
        day: The calendar day to take the first instant of.

    Returns:
        datetime: Midnight starting ``day``, naive, as ``users.created_at``
        stores it.
    """
    return datetime(day.year, day.month, day.day)


def days_of(series: CreatedPerDayResponse) -> list[date]:
    """The calendar days of a series, in the order it answers them.

    Args:
        series: The series a service function returned.

    Returns:
        list[date]: One day per data point, oldest first.
    """
    return [point.date for point in series.root]


def counts_of(series: CreatedPerDayResponse) -> dict[date, int]:
    """The series as a day-to-count mapping, for reading off individual days.

    Args:
        series: The series a service function returned.

    Returns:
        dict[date, int]: Each data point's count, keyed by its day.
    """
    return {point.date: point.count for point in series.root}


def _imported_modules(module: Path) -> list[str]:
    """List the modules a source file imports, as they are written.

    Args:
        module: The file to read.

    Returns:
        list[str]: One dotted module name per ``import`` or ``from ... import``
        in the file, so an architecture boundary can be checked against the
        imports themselves rather than against the prose around them.
    """
    names: list[str] = []
    for node in ast.walk(ast.parse(module.read_text())):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def _tool(name: str) -> list[str]:
    """The command line that runs a project-configured tool.

    Args:
        name: The tool's executable name, e.g. ``"ruff"``.

    Returns:
        list[str]: The command, preferring the project's own virtualenv.
    """
    local = PROJECT_ROOT / ".venv" / "bin" / name
    if local.exists():
        return [str(local)]
    return [sys.executable, "-m", name]  # pragma: no cover - fallback


class TestSevenDayWindow:
    """AC-001: the service calculates the seven-day window itself."""

    def test_the_window_spans_seven_days(self) -> None:
        """Seven days is the window, named once and used everywhere."""
        assert DAILY_WINDOW_DAYS == WINDOW_DAYS
        assert len(daily_window()) == WINDOW_DAYS

    def test_the_window_ends_today_and_runs_oldest_first(self) -> None:
        """The last day is today (UTC) and the first is six days before it."""
        today = utc_today()
        window = daily_window()

        assert window[0] == today - timedelta(days=WINDOW_DAYS - 1)
        assert window[-1] == today
        assert window == [today - timedelta(days=offset) for offset in range(6, -1, -1)]

    def test_the_window_is_contiguous_and_never_repeats_a_day(self) -> None:
        """One day at a time, with no gap and no day twice."""
        window = daily_window()

        assert len(set(window)) == WINDOW_DAYS
        assert all(
            later - earlier == timedelta(days=1)
            for earlier, later in zip(window, window[1:], strict=False)
        )

    def test_an_explicit_end_date_anchors_the_window(self) -> None:
        """A named end day gives the seven days ending on it, oldest first."""
        last_day = date(2026, 3, 1)

        assert daily_window(end_date=last_day) == [
            last_day - timedelta(days=offset) for offset in range(6, -1, -1)
        ]

    def test_a_window_below_one_day_is_refused(self) -> None:
        """Zero or negative days describe no window, and say so."""
        for days in (0, -1):
            with pytest.raises(ValueError, match="at least one day"):
                daily_window(days=days)

    def test_the_bounds_cover_the_window_and_nothing_more(self) -> None:
        """The half-open range spans the first day to the end of the last."""
        last_day = date(2026, 3, 1)
        window = daily_window(end_date=last_day)

        start, end = window_bounds(window)

        assert start == at_midnight(last_day - timedelta(days=WINDOW_DAYS - 1))
        assert end == at_midnight(last_day + timedelta(days=1))
        assert end > start

    def test_a_descending_window_is_refused(self) -> None:
        """A window that does not ascend cannot bound a query, and says so."""
        window = [date(2026, 3, 1), date(2026, 2, 28)]

        with pytest.raises(ValueError, match="ascend"):
            window_bounds(window)

    def test_an_empty_window_is_refused(self) -> None:
        """An empty window would answer no data points at all, and says so."""
        with pytest.raises(ValueError, match="at least one day"):
            window_bounds([])


class TestSeriesIsBuiltWithoutADatabase:
    """AC-001/AC-002: the series is assembled from plain data, no session needed."""

    def test_every_day_of_the_window_gets_a_data_point(self) -> None:
        """The window, not the rows, decides how many data points come back."""
        window = daily_window(end_date=date(2026, 3, 1))

        series = build_daily_series([], window=window)

        assert days_of(series) == window
        assert counts_of(series) == dict.fromkeys(window, 0)

    def test_days_with_no_creation_read_as_zero(self) -> None:
        """A counted day is reported; the rest of the window is zero, not absent."""
        last_day = date(2026, 3, 1)
        window = daily_window(end_date=last_day)
        counted_day = last_day - timedelta(days=2)

        series = build_daily_series([(counted_day, 4)], window=window)

        assert counts_of(series)[counted_day] == 4
        assert sum(counts_of(series).values()) == 4

    def test_rows_outside_the_window_are_dropped(self) -> None:
        """A count for a day the window does not cover is not answered."""
        last_day = date(2026, 3, 1)
        window = daily_window(end_date=last_day)
        outside = last_day - timedelta(days=40)

        series = build_daily_series([(outside, 9), (last_day, 1)], window=window)

        assert days_of(series) == window
        assert outside not in counts_of(series)

    def test_the_series_is_ordered_oldest_first(self) -> None:
        """Rows handed over out of order still answer an ascending series."""
        last_day = date(2026, 3, 1)
        window = daily_window(end_date=last_day)
        rows = [(day, 1) for day in reversed(window)]

        series = build_daily_series(rows, window=window)

        assert days_of(series) == sorted(window)

    def test_a_mapping_of_counts_is_accepted_as_well_as_rows(self) -> None:
        """The service takes rows or a day-to-count mapping, either way one shape."""
        last_day = date(2026, 3, 1)
        window = daily_window(end_date=last_day)
        counted: Mapping[date, int] = {last_day: 3}

        series = build_daily_series(counted, window=window)

        assert counts_of(series)[last_day] == 3

    def test_the_window_can_be_left_to_the_service(self) -> None:
        """Asking without a window gets the seven days ending today (UTC)."""
        today = utc_today()

        series = build_daily_series([(today, 2)])

        assert days_of(series) == daily_window()
        assert counts_of(series)[today] == 2

    def test_an_empty_window_cannot_build_a_series(self) -> None:
        """A series needs a window; an empty one is refused, not answered empty."""
        with pytest.raises(ValueError, match="at least one day"):
            build_daily_series([], window=[])


class TestIso8601Formatting:
    """AC-002: every data point is an ISO-8601 calendar date."""

    def test_data_points_serialise_as_iso_8601_calendar_days(self) -> None:
        """The JSON body carries ``YYYY-MM-DD``, with no time component."""
        last_day = date(2026, 3, 1)
        window = daily_window(end_date=last_day)

        body = build_daily_series([(last_day, 2)], window=window).model_dump(
            mode="json"
        )

        assert isinstance(body, list)
        for point in body:
            assert set(point) == {"date", "count"}
            assert len(point["date"]) == len("2026-03-01")
            assert date.fromisoformat(point["date"]).isoformat() == point["date"]
        assert body[-1] == {"date": "2026-03-01", "count": 2}

    def test_iso_date_formats_a_calendar_day(self) -> None:
        """A day formats as its ISO-8601 date."""
        assert iso_date(date(2026, 9, 8)) == "2026-09-08"

    def test_iso_date_formats_a_timestamp_as_the_day_it_falls_on(self) -> None:
        """A timestamp is reduced to its day before it is formatted."""
        assert iso_date(datetime(2026, 9, 8, 23, 59, 59)) == "2026-09-08"

    def test_iso_date_accepts_an_iso_8601_string(self) -> None:
        """A day that arrives as text round-trips to the same text."""
        assert iso_date("2026-09-08") == "2026-09-08"
        assert iso_date("2026-09-08T06:30:00") == "2026-09-08"

    def test_a_day_is_read_from_every_shape_the_databases_answer_with(self) -> None:
        """PostgreSQL answers a date, SQLite a string, an expression a timestamp."""
        expected = date(2026, 9, 8)

        assert to_calendar_day(expected) == expected
        assert to_calendar_day(datetime(2026, 9, 8, 12, 0)) == expected
        assert to_calendar_day("2026-09-08") == expected
        assert to_calendar_day(" 2026-09-08 ") == expected

    def test_a_day_that_is_not_an_iso_8601_date_is_refused(self) -> None:
        """Unparseable text is reported as itself, not silently read as another day."""
        with pytest.raises(ValueError, match="ISO-8601"):
            to_calendar_day("09/08/2026")

    def test_a_day_of_the_wrong_type_is_refused(self) -> None:
        """A count cannot be mistaken for a day, and the error names the type."""
        with pytest.raises(TypeError, match="int"):
            to_calendar_day(cast(object, 20260908))

    def test_a_data_point_carries_the_day_and_a_non_negative_count(self) -> None:
        """The formatting step produces the contract's data point, validated."""
        point = format_data_point(datetime(2026, 9, 8, 12, 0), 5)

        assert point.date == date(2026, 9, 8)
        assert point.count == 5

    def test_a_negative_count_is_refused(self) -> None:
        """A negative count is a broken row, not a data point, and says which day."""
        with pytest.raises(ValueError, match="2026-09-08"):
            format_data_point(date(2026, 9, 8), -1)


class TestRetrievalIsOrchestrated:
    """The service, not the router, drives the retrieval and the formatting."""

    async def test_the_query_is_asked_for_exactly_the_window(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The bounds handed to the query are the window's first and last edges."""
        today = utc_today()
        asked: dict[str, datetime] = {}

        async def fake_count(
            _db: AsyncSession, start: datetime, end: datetime
        ) -> list[tuple[date, int]]:
            """Stand in for the query layer, recording the bounds it was given."""
            asked["start"] = start
            asked["end"] = end
            return [(today, 2)]

        monkeypatch.setattr(
            analytics_service, "count_users_created_per_day", fake_count
        )

        series = await get_users_created_per_day(cast("AsyncSession", None))

        assert asked["start"] == at_midnight(today - timedelta(days=WINDOW_DAYS - 1))
        assert asked["end"] == at_midnight(today + timedelta(days=1))
        assert days_of(series) == daily_window()
        assert counts_of(series)[today] == 2

    async def test_the_series_never_answers_more_or_fewer_than_seven_days(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rows far outside the window neither lengthen nor shorten the reply."""

        async def far_rows(
            _db: AsyncSession, _start: datetime, _end: datetime
        ) -> list[tuple[date, int]]:
            """Answer rows that straddle the window on both sides."""
            far_past = utc_today() - timedelta(days=40)
            far_future = utc_today() + timedelta(days=40)
            return [(far_past, 5), (far_future, 7)]

        monkeypatch.setattr(analytics_service, "count_users_created_per_day", far_rows)

        series = await get_users_created_per_day(cast("AsyncSession", None))

        assert len(series.root) == WINDOW_DAYS
        assert all(count == 0 for count in counts_of(series).values())

    async def test_a_failing_query_is_reported_not_swallowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A database that refuses surfaces as an error, never a short series."""

        async def refuse(
            _db: AsyncSession, _start: datetime, _end: datetime
        ) -> list[tuple[date, int]]:
            """Stand in for a database that fails the query."""
            raise SQLAlchemyError("database refused the daily-count query")

        monkeypatch.setattr(analytics_service, "count_users_created_per_day", refuse)

        with pytest.raises(SQLAlchemyError, match="refused"):
            await get_users_created_per_day(cast("AsyncSession", None))

    def test_the_endpoint_serves_the_service_layer(self) -> None:
        """The router answers through this service, not around it.

        The router imports the name into its own namespace, so what is checked
        is that the function behind the route is this module's.
        """
        served = vars(analytics_router)["get_users_created_per_day"]

        assert served is analytics_service.get_users_created_per_day
        assert served.__module__ == "src.analytics.service"

    def test_the_service_reaches_users_through_their_public_read_interface(
        self,
    ) -> None:
        """ADR-001: the service aggregates via ``src.users.crud``, never its models."""
        read_function = analytics_service.count_users_created_per_day

        assert read_function.__module__ == "src.users.crud"

        imported = _imported_modules(PROJECT_ROOT / "src" / "analytics" / "service.py")

        assert "src.users.crud" in imported
        assert [name for name in imported if name.startswith("src.users.models")] == []


class TestChecksOnModifiedFiles:
    """AC-003: the files this task touches pass the configured lint/format gates."""

    def test_ruff_check_reports_no_errors(self) -> None:
        """`ruff check` (E, F, I, UP per pyproject) is clean on both files."""
        result = subprocess.run(
            [*_tool("ruff"), "check", *MODIFIED_FILES],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr

    def test_ruff_format_reports_no_rewrites(self) -> None:
        """`ruff format --check` would leave both files untouched."""
        result = subprocess.run(
            [*_tool("ruff"), "format", "--check", *MODIFIED_FILES],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr


class TestServiceKeepsItsShape:
    """The service layer is importable and its public names are declared."""

    def test_the_public_names_are_declared(self) -> None:
        """``__all__`` names the service's interface, and every name exists."""
        for name in analytics_service.__all__:
            assert hasattr(analytics_service, name), name

        assert "get_users_created_per_day" in analytics_service.__all__
        assert "build_daily_series" in analytics_service.__all__

    def test_the_window_constant_is_the_one_the_query_layer_uses(self) -> None:
        """One window is declared for the package, not one per layer."""
        from src.analytics import crud as analytics_crud

        assert analytics_service.DAILY_WINDOW_DAYS is analytics_crud.DAILY_WINDOW_DAYS

    def test_no_database_is_needed_to_import_or_run_the_service(self) -> None:
        """The service layer holds no session of its own; the caller supplies one."""
        signature = inspect.signature(get_users_created_per_day)

        assert "db" in signature.parameters

    def test_the_service_returns_the_documented_schema_type(self) -> None:
        """The series the service builds is the endpoint's response contract."""
        series = build_daily_series([], window=daily_window())

        assert isinstance(series, CreatedPerDayResponse)
