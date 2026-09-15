"""Tests for the analytics CRUD layer (TASK-6F3D-002).

Covers the acceptance criteria of TASK-6F3D-002:

- AC-001: the query returns exactly 7 days of data
- AC-002: the data points are ordered oldest to newest
- AC-003: the modified files pass the project-configured lint/format checks
  (ruff check and ruff format --check, the checks pyproject.toml configures,
  run over the files this task touched)

The tests run against whichever database the harness settled for the run —
in-memory SQLite by default, PostgreSQL under qa/run-suite.sh — so the
day-grouping query is exercised on the dialect the endpoint actually ships on,
not only on the one that forgives a dialect-only function.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.analytics import crud as analytics_crud
from src.analytics.crud import (
    DAILY_WINDOW_DAYS,
    daily_window,
    get_users_created_per_day,
)
from src.users import crud
from src.users.schemas import UserCreate

PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: The files TASK-6F3D-002 writes, relative to the repository root. The new
#: query layer, and the one existing file it extends with a public read
#: function (ADR-001 amendment: analytics reads users through users/crud.py).
MODIFIED_FILES = ("src/analytics/crud.py", "src/users/crud.py")


def utc_today() -> date:
    """Today's UTC date, worked out here rather than imported.

    Importing ``src.analytics.crud.utc_today`` would grade the implementation
    against itself, so the tests derive the day the same way the feature spec
    describes it: the current day in UTC.

    Returns:
        date: The current UTC calendar day.
    """
    return datetime.now(tz=UTC).date()


def at_noon(day: date) -> datetime:
    """A timestamp in the middle of a day, so no boundary is being tested.

    Args:
        day: The calendar day to place the timestamp on.

    Returns:
        datetime: Noon on ``day``, naive, as ``users.created_at`` stores it.
    """
    return datetime(day.year, day.month, day.day, 12, 0)


def at_midnight(day: date) -> datetime:
    """The first instant of a day, so window edges can be tested on purpose.

    Args:
        day: The calendar day to take the first instant of.

    Returns:
        datetime: Midnight starting ``day``, naive, as the column stores it.
    """
    return datetime(day.year, day.month, day.day)


async def seed_user(
    db: AsyncSession, local_part: str, created_at: datetime, *, deleted: bool = False
) -> None:
    """Create a user whose creation timestamp is exactly ``created_at``.

    Args:
        db: The session to write through.
        local_part: The local part of a unique email address.
        created_at: Naive UTC timestamp to stamp the row with.
        deleted: Whether to soft-delete the user as well.
    """
    user = await crud.create_user(
        db, UserCreate(email=f"{local_part}@example.com", full_name="Seeded")
    )
    user.created_at = created_at
    if deleted:
        user.deleted_at = created_at
    await db.flush()
    await db.refresh(user)


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


class TestDailyWindow:
    """AC-001/AC-002: the window the query answers, before any rows exist."""

    def test_the_window_spans_seven_days(self) -> None:
        """The default window is seven days, the number the endpoint promises."""
        assert DAILY_WINDOW_DAYS == 7
        assert len(daily_window()) == 7

    def test_the_window_runs_oldest_first_and_is_contiguous(self) -> None:
        """The window is one day at a time, oldest day at the front."""
        window = daily_window()

        assert window == sorted(window)
        assert window == [window[0] + timedelta(days=offset) for offset in range(7)]

    def test_the_window_ends_today_when_no_day_is_given(self) -> None:
        """'The last 7 days' ends at the current UTC day."""
        window = daily_window()

        assert window[-1] == utc_today()
        assert window[0] == utc_today() - timedelta(days=6)

    def test_the_window_ends_on_the_requested_day(self) -> None:
        """An explicit end date moves the whole window, seven days wide."""
        window = daily_window(end_date=date(2026, 9, 14))

        assert len(window) == 7
        assert window[-1] == date(2026, 9, 14)
        assert window[0] == date(2026, 9, 8)

    @pytest.mark.parametrize("days", [0, -1])
    def test_a_window_that_spans_no_day_is_refused(self, days: int) -> None:
        """A window of zero or fewer days is a bad argument, said out loud."""
        with pytest.raises(ValueError, match="at least one day"):
            daily_window(days=days)


class TestCountUsersCreatedPerDay:
    """The users-feature read function the analytics query depends on."""

    async def test_only_days_with_creations_come_back_oldest_first(
        self, db_session: AsyncSession
    ) -> None:
        """The grouped query reports the days that have rows, oldest first."""
        today = utc_today()
        start_day = today - timedelta(days=6)
        await seed_user(db_session, "one-a", at_noon(start_day))
        await seed_user(db_session, "one-b", at_noon(start_day))
        await seed_user(db_session, "later", at_noon(start_day + timedelta(days=3)))

        rows = await crud.count_users_created_per_day(
            db_session,
            start=at_midnight(start_day),
            end=at_midnight(today) + timedelta(days=1),
        )

        assert rows == [(start_day, 2), (start_day + timedelta(days=3), 1)]

    @pytest.mark.parametrize("offset", [0, 1])
    async def test_a_window_that_does_not_ascend_is_refused(
        self, db_session: AsyncSession, offset: int
    ) -> None:
        """start must fall strictly before end; a flat or backwards window is
        a caller mistake, not an empty answer."""
        now = at_noon(utc_today())
        with pytest.raises(ValueError, match="must ascend"):
            await crud.count_users_created_per_day(
                db_session, start=now, end=now - timedelta(days=offset)
            )

    async def test_soft_deleted_users_are_not_counted(
        self, db_session: AsyncSession
    ) -> None:
        """A creation that was later deleted is no longer a creation, matching
        every other count in this feature."""
        today = utc_today()
        await seed_user(db_session, "kept", at_noon(today))
        await seed_user(db_session, "gone", at_noon(today), deleted=True)

        rows = await crud.count_users_created_per_day(
            db_session, start=at_noon(today), end=at_noon(today + timedelta(days=1))
        )

        assert rows == [(today, 1)]


class TestUsersCreatedPerDayQuery:
    """AC-001 and AC-002: the daily series the analytics layer answers with."""

    async def test_an_empty_database_still_answers_seven_days(
        self, db_session: AsyncSession
    ) -> None:
        """AC-001: seven data points, all zero — the window is not a filter."""
        series = await get_users_created_per_day(db_session)

        assert len(series.root) == 7
        assert [point.count for point in series.root] == [0] * 7

    async def test_seven_days_are_returned_when_rows_exist(
        self, db_session: AsyncSession
    ) -> None:
        """AC-001: the count of data points stays at seven whatever the rows."""
        today = utc_today()
        for offset, how_many in ((0, 3), (2, 2), (6, 1)):
            for index in range(how_many):
                await seed_user(
                    db_session,
                    f"day{offset}-{index}",
                    at_noon(today - timedelta(days=offset)),
                )

        series = await get_users_created_per_day(db_session)

        assert len(series.root) == 7

    async def test_every_day_of_the_window_carries_its_own_count(
        self, db_session: AsyncSession
    ) -> None:
        """AC-001: each day reports its own creations, zero included."""
        today = utc_today()
        for offset, how_many in ((0, 3), (2, 2), (6, 1)):
            for index in range(how_many):
                await seed_user(
                    db_session,
                    f"count{offset}-{index}",
                    at_noon(today - timedelta(days=offset)),
                )

        series = await get_users_created_per_day(db_session)

        expected = {
            today: 3,
            today - timedelta(days=2): 2,
            today - timedelta(days=6): 1,
        }
        assert [(point.date, point.count) for point in series.root] == [
            (day, expected.get(day, 0)) for day in daily_window(end_date=today, days=7)
        ]

    async def test_the_data_points_run_oldest_to_newest(
        self, db_session: AsyncSession
    ) -> None:
        """AC-002: strictly ascending, one point per day, oldest at the front."""
        today = utc_today()
        for index, offset in enumerate((5, 1, 3, 1)):
            await seed_user(
                db_session,
                f"order{offset}-{index}",
                at_noon(today - timedelta(days=offset)),
            )

        series = await get_users_created_per_day(db_session)
        days = [point.date for point in series.root]

        assert days == sorted(days)
        assert days == [today - timedelta(days=offset) for offset in range(6, -1, -1)]
        assert all(
            later > earlier for earlier, later in zip(days, days[1:], strict=False)
        )

    async def test_the_newest_data_point_is_today(
        self, db_session: AsyncSession
    ) -> None:
        """AC-002: the series ends at the current UTC day, not at the newest row."""
        await seed_user(db_session, "old", at_noon(utc_today() - timedelta(days=4)))

        series = await get_users_created_per_day(db_session)

        assert series.root[-1].date == utc_today()

    async def test_creations_older_than_the_window_are_left_out(
        self, db_session: AsyncSession
    ) -> None:
        """AC-001: the window is exactly seven days, not 'everything so far'."""
        today = utc_today()
        await seed_user(db_session, "inside", at_noon(today - timedelta(days=6)))
        await seed_user(db_session, "outside", at_noon(today - timedelta(days=7)))
        await seed_user(db_session, "long-gone", at_noon(today - timedelta(days=30)))

        series = await get_users_created_per_day(db_session)

        assert len(series.root) == 7
        # Oldest first: the day six days back leads the series, today closes it.
        assert [point.count for point in series.root] == [1, 0, 0, 0, 0, 0, 0]

    async def test_a_creation_at_the_first_instant_of_a_day_is_counted(
        self, db_session: AsyncSession
    ) -> None:
        """AC-001: the window is half-open, so midnight belongs to its own day."""
        today = utc_today()
        midnight = datetime(today.year, today.month, today.day, 0, 0, 0)
        await seed_user(db_session, "midnight", midnight)

        series = await get_users_created_per_day(db_session)

        assert series.root[-1].count == 1

    async def test_the_end_date_moves_the_window(
        self, db_session: AsyncSession
    ) -> None:
        """AC-001/AC-002: an explicit end date still answers seven ordered days."""
        end = date(2026, 9, 14)
        await seed_user(db_session, "then", at_noon(end))
        await seed_user(db_session, "after", at_noon(end + timedelta(days=1)))

        series = await get_users_created_per_day(db_session, end_date=end)

        assert [point.date for point in series.root] == daily_window(end_date=end)
        assert [point.count for point in series.root] == [0, 0, 0, 0, 0, 0, 1]

    @pytest.mark.parametrize("days", [1, 3, 10])
    async def test_the_window_size_is_the_number_of_data_points(
        self, db_session: AsyncSession, days: int
    ) -> None:
        """AC-001: 'exactly N days' holds for any window the caller asks for."""
        series = await get_users_created_per_day(db_session, days=days)

        assert len(series.root) == days

    async def test_the_series_is_the_response_body_the_contract_names(
        self, db_session: AsyncSession
    ) -> None:
        """AC-001/AC-002: the artifact is a JSON array of date/count pairs."""
        await seed_user(db_session, "shape", at_noon(utc_today()))

        series = await get_users_created_per_day(db_session)
        body = json.loads(series.model_dump_json())

        assert isinstance(body, list)
        assert len(body) == 7
        assert all(sorted(item) == ["count", "date"] for item in body)
        assert [item["date"] for item in body] == sorted(item["date"] for item in body)


class TestReadInterfaceBoundary:
    """AC-002's supporting boundary: analytics still reads users the legal way.

    ADR-001 (amendment of 2026-08-31) lets one feature import another's
    ``crud.py`` and ``schemas.py`` and nothing else, so the new query layer must
    reach the users table through ``src.users.crud``.
    """

    def test_the_query_layer_reads_users_through_crud(self) -> None:
        """The analytics query layer imports the users read interface."""
        tree = ast.parse(
            (PROJECT_ROOT / "src" / "analytics" / "crud.py").read_text(encoding="utf-8")
        )
        imported = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }

        assert "src.users.crud" in imported
        assert not any(name.startswith("src.users.models") for name in imported)

    def test_the_read_function_is_public(self) -> None:
        """The function analytics depends on belongs to users' crud.py."""
        read_function = crud.count_users_created_per_day

        assert read_function.__module__ == "src.users.crud"
        assert not read_function.__name__.startswith("_")
        # The analytics module reaches users through that function, not around it.
        assert vars(analytics_crud)["count_users_created_per_day"] is read_function


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
