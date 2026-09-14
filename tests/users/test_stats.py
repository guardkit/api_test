"""Endpoint tests for the daily user-creation counts (TASK-D49B-005, FEAT-D49B).

This is the endpoint test file of the feature. It asks
``GET /users/created-per-day`` over HTTP — through the application the process
serves, not a stand-in router — and pins what
``features/daily-user-creation-count/daily-user-creation-count.feature`` says
about the answer:

* AC-001 exactly seven data points — ``TestExactlySevenDataPoints``
* AC-002 the oldest day is the first entry — ``TestOldestDayIsFirst``
* AC-003 the most recent day is the last entry — ``TestMostRecentDayIsLast``
* AC-004 a POST request is rejected — ``TestPostIsRejected``
* AC-005 zero counts when no users were created — ``TestZeroCountsOnEmptyData``
* AC-006 the current day is included even when incomplete —
  ``TestCurrentDayIsIncluded``
* AC-007 the response body is a JSON array — ``TestBodyIsJsonArray``

Owned elsewhere in this feature, and deliberately not restated here:

* the SQL and the window's arithmetic — TASK-D49B-002, in
  ``tests/users/test_stats_crud.py``;
* the route's registration and its dependency graph — TASK-D49B-003, in
  ``tests/users/test_created_per_day_router.py``;
* the ``(date, count)`` schemas — TASK-D49B-001, in
  ``tests/users/test_stats_schemas.py``.

Every assertion below is a lasting invariant: something this feature is
specified to keep. No test asserts that a route, method, file or directory a
later task of this feature will add is absent, and none asserts that anything
raises ``NotImplementedError``.

Two things keep the run honest about *when* and *where* it runs. Expected days
are derived from ``date.today()`` — the same clock the read model reads — so the
assertions hold on whichever day the suite runs, including the moments when the
window rolls over. And nothing in this file reads an environment variable: the
database arrives through the suite's own fixtures (``tests/conftest.py``, which
settles SQLite or PostgreSQL before the application is imported), so no test's
outcome can shift with the host environment, and no failure diff can print live
ambient values.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta
from http import HTTPStatus
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dependencies import get_db as dependencies_get_db
from src.db.session import get_async_session
from src.db.session import get_db as session_get_db
from src.main import app
from src.users import crud
from src.users.schemas import UserCreate

ENDPOINT = "/users/created-per-day"

# The window the feature specifies: the current day plus the six days before it,
# reported oldest first (ASSUM-001 and ASSUM-002 of
# features/daily-user-creation-count). It is spelled out here rather than
# imported from src.users.stats, so the endpoint is pinned to the specification
# and not to a constant the implementation happens to hold today.
WINDOW_DAYS = 7

# Every session provider this application recognises. Overriding all three means
# these tests exercise the handler whichever of the allowed ways it takes its
# session (ADR-006 in docs/architecture-rules.yaml), so a later task that moves
# the handler onto the AsyncSessionDep alias cannot leave a test here reading a
# database nobody meant it to read.
DB_SESSION_PROVIDERS = (dependencies_get_db, session_get_db, get_async_session)


def _window(days: int = WINDOW_DAYS) -> list[date]:
    """Return the window the endpoint must report: ``days`` days ending today.

    Args:
        days: How many days the window spans, the current day included.

    Returns:
        ``days`` consecutive calendar days, oldest first, ending with today.
    """
    today = date.today()
    return [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def _entries(response: Response) -> list[dict[str, Any]]:
    """Return a daily-count response body as a list of ``{date, count}`` entries.

    A body that is not the shape the endpoint documents fails here, where the
    message says what arrived, rather than three assertions later as a confusing
    type error.

    Args:
        response: A served ``GET /users/created-per-day`` response.

    Returns:
        The entries, in the order the response carries them.

    Raises:
        AssertionError: If the body is not an array of ``{date, count}`` objects
            carrying integer counts, which is itself the failure to report.
    """
    body = response.json()
    assert isinstance(body, list), (
        f"expected a JSON array of entries, got {type(body).__name__}: {body!r}"
    )
    entries: list[dict[str, Any]] = []
    for entry in body:
        assert isinstance(entry, dict), f"expected an object entry, got {entry!r}"
        assert set(entry) == {"date", "count"}, (
            f"an entry is a (date, count) pair, got keys {sorted(entry)}: {entry!r}"
        )
        count = entry["count"]
        assert isinstance(count, int) and not isinstance(count, bool), (
            f"a count is a JSON integer, got {count!r}"
        )
        entries.append(entry)
    return entries


def _days_of(response: Response) -> list[date]:
    """Return the days a daily-count response reports, oldest entry first.

    Args:
        response: A served ``GET /users/created-per-day`` response.

    Returns:
        One calendar day per entry, in the order the response carries them.
    """
    return [date.fromisoformat(str(entry["date"])) for entry in _entries(response)]


def _counts_by_day(response: Response) -> dict[date, int]:
    """Turn a daily-count response into a ``{day: count}`` mapping.

    Args:
        response: A served ``GET /users/created-per-day`` response.

    Returns:
        The reported days mapped to the counts reported for them.
    """
    return {
        date.fromisoformat(str(entry["date"])): int(entry["count"])
        for entry in _entries(response)
    }


async def _create_user_created_at(
    db_session: AsyncSession, email: str, created_at: datetime
) -> None:
    """Create a user whose ``created_at`` is pinned to ``created_at``.

    Args:
        db_session: The session to create through.
        email: Unique email for the new user.
        created_at: The timestamp the user appears to have been created at.

    Returns:
        None.
    """
    user = await crud.create_user(
        db_session, UserCreate(email=email, full_name=email.split("@", 1)[0])
    )
    user.created_at = created_at
    await db_session.flush()


async def _create_user_created_on(
    db_session: AsyncSession, email: str, day: date, hour: int = 12
) -> None:
    """Create a user that appears to have been created on ``day`` at ``hour``.

    Args:
        db_session: The session to create through.
        email: Unique email for the new user.
        day: The calendar day the user appears to have been created on.
        hour: Hour of that day to stamp (default noon).

    Returns:
        None.
    """
    await _create_user_created_at(
        db_session, email, datetime(day.year, day.month, day.day, hour, 0, 0)
    )


@pytest.fixture
async def endpoint_client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Yield an ASGI client whose requests are served from this test's session.

    Args:
        db_session: The per-test database session.

    Yields:
        AsyncClient: A client that talks to the application over ASGI, with no
        network and no server involved.
    """

    async def provider() -> AsyncIterator[AsyncSession]:
        yield db_session

    for provider_key in DB_SESSION_PROVIDERS:
        app.dependency_overrides[provider_key] = provider
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        for provider_key in DB_SESSION_PROVIDERS:
            app.dependency_overrides.pop(provider_key, None)


class TestExactlySevenDataPoints:
    """AC-001: the response contains exactly seven data points."""

    async def test_seven_entries_come_back_from_a_quiet_database(
        self, endpoint_client: AsyncClient
    ) -> None:
        """Seven days are reported whether or not anyone was created on them.

        Args:
            endpoint_client: an ASGI client served from this test's session.

        Returns:
            None.
        """
        response = await endpoint_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        assert len(_entries(response)) == WINDOW_DAYS

    async def test_seven_entries_come_back_when_the_days_hold_data(
        self, endpoint_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Populating the window neither adds nor drops an entry: still seven.

        Args:
            endpoint_client: an ASGI client served from this test's session.
            db_session: the per-test database session.

        Returns:
            None.
        """
        today = date.today()
        await _create_user_created_on(db_session, "today@example.com", today)
        await _create_user_created_on(
            db_session, "four-days-ago@example.com", today - timedelta(days=4)
        )

        response = await endpoint_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        assert len(_entries(response)) == WINDOW_DAYS

    async def test_the_seven_entries_are_seven_consecutive_days(
        self, endpoint_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Seven distinct days, one after another, with no gap and no repeat.

        Args:
            endpoint_client: an ASGI client served from this test's session.
            db_session: the per-test database session.

        Returns:
            None.
        """
        await _create_user_created_on(db_session, "someone@example.com", date.today())

        days = _days_of(await endpoint_client.get(ENDPOINT))

        assert len(days) == WINDOW_DAYS
        assert len(set(days)) == len(days), f"a day is reported twice: {days}"
        assert days == _window(), f"days are not a run of consecutive dates: {days}"


class TestOldestDayIsFirst:
    """AC-002: the oldest day of the window is the first entry in the list."""

    async def test_the_first_entry_is_the_oldest_day_of_the_window(
        self, endpoint_client: AsyncClient
    ) -> None:
        """The first entry is six days back, the window's oldest day.

        Args:
            endpoint_client: an ASGI client served from this test's session.

        Returns:
            None.
        """
        days = _days_of(await endpoint_client.get(ENDPOINT))

        assert days[0] == date.today() - timedelta(days=WINDOW_DAYS - 1)
        assert days[0] == min(days), f"the first entry is not the oldest day: {days}"

    async def test_the_first_entry_stays_the_oldest_day_once_days_hold_data(
        self, endpoint_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Data does not reorder the list: the window's oldest day stays first.

        The users are written newest first, so a listing that followed insertion
        order would put today at the front and fail here.

        Args:
            endpoint_client: an ASGI client served from this test's session.
            db_session: the per-test database session.

        Returns:
            None.
        """
        today = date.today()
        for offset in (0, 2, WINDOW_DAYS - 1):
            await _create_user_created_on(
                db_session,
                f"offset-{offset}@example.com",
                today - timedelta(days=offset),
            )

        response = await endpoint_client.get(ENDPOINT)

        days = _days_of(response)
        assert days[0] == min(days) == today - timedelta(days=WINDOW_DAYS - 1)
        assert _counts_by_day(response)[days[0]] == 1

    async def test_the_response_holds_no_data_older_than_the_window(
        self, endpoint_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Nothing before the first entry's day is reported at all.

        Args:
            endpoint_client: an ASGI client served from this test's session.
            db_session: the per-test database session.

        Returns:
            None.
        """
        today = date.today()
        await _create_user_created_on(db_session, "in-window@example.com", today)
        await _create_user_created_on(
            db_session, "eight-days-ago@example.com", today - timedelta(days=8)
        )
        await _create_user_created_on(
            db_session, "a-year-ago@example.com", today - timedelta(days=365)
        )

        response = await endpoint_client.get(ENDPOINT)

        days = _days_of(response)
        assert min(days) == today - timedelta(days=WINDOW_DAYS - 1)
        assert sum(_counts_by_day(response).values()) == 1


class TestMostRecentDayIsLast:
    """AC-003: the most recent day is the last entry in the list."""

    async def test_the_last_entry_is_the_most_recent_day_of_the_window(
        self, endpoint_client: AsyncClient
    ) -> None:
        """The last entry is the newest day the window holds.

        Args:
            endpoint_client: an ASGI client served from this test's session.

        Returns:
            None.
        """
        days = _days_of(await endpoint_client.get(ENDPOINT))

        assert days[-1] == date.today()
        assert days[-1] == max(days), f"the last entry is not the newest day: {days}"

    async def test_the_dates_strictly_ascend_from_first_entry_to_last(
        self, endpoint_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Oldest to newest is a total order over the list, not only at the ends.

        Args:
            endpoint_client: an ASGI client served from this test's session.
            db_session: the per-test database session.

        Returns:
            None.
        """
        today = date.today()
        for offset in (5, 1, 3):
            await _create_user_created_on(
                db_session,
                f"ascend-{offset}@example.com",
                today - timedelta(days=offset),
            )

        days = _days_of(await endpoint_client.get(ENDPOINT))

        assert days == sorted(days)
        assert days == sorted(set(days)), f"dates must strictly ascend: {days}"

    async def test_the_last_day_holding_data_is_the_most_recent_creation(
        self, endpoint_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Seen by count as well: no day after the newest creation reports one.

        Args:
            endpoint_client: an ASGI client served from this test's session.
            db_session: the per-test database session.

        Returns:
            None.
        """
        today = date.today()
        oldest = today - timedelta(days=WINDOW_DAYS - 1)
        newest_with_data = today - timedelta(days=2)
        await _create_user_created_on(db_session, "oldest@example.com", oldest)
        await _create_user_created_on(
            db_session, "newest@example.com", newest_with_data
        )

        counts = _counts_by_day(await endpoint_client.get(ENDPOINT))

        days_with_data = [day for day, count in counts.items() if count > 0]
        assert max(days_with_data) == newest_with_data
        assert counts[oldest] == 1


class TestPostIsRejected:
    """AC-004: a POST request to the endpoint is rejected."""

    async def test_a_post_to_the_endpoint_is_refused(
        self, endpoint_client: AsyncClient
    ) -> None:
        """POST is refused as the wrong method, and answers nothing about days.

        Args:
            endpoint_client: an ASGI client served from this test's session.

        Returns:
            None.
        """
        response = await endpoint_client.post(ENDPOINT)

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
        assert response.status_code >= HTTPStatus.BAD_REQUEST

    async def test_a_rejected_post_creates_no_user(
        self, endpoint_client: AsyncClient
    ) -> None:
        """Rejection means no write happened: the window still reads all zeros.

        Args:
            endpoint_client: an ASGI client served from this test's session.

        Returns:
            None.
        """
        await endpoint_client.post(ENDPOINT, json={"email": "nobody@example.com"})

        counts = _counts_by_day(await endpoint_client.get(ENDPOINT))

        assert len(counts) == WINDOW_DAYS
        assert set(counts.values()) == {0}

    async def test_the_endpoint_offers_get_alone(self) -> None:
        """Only GET is offered on the path, which is why other methods are refused.

        Returns:
            None.
        """
        path_item = app.openapi()["paths"][ENDPOINT]

        assert "get" in path_item, f"no GET operation on {ENDPOINT}: {path_item}"
        assert "post" not in path_item, f"{ENDPOINT} must not accept POST"


class TestZeroCountsOnEmptyData:
    """AC-005: the response contains zero counts when no users were created."""

    async def test_an_empty_database_answers_seven_zero_counts(
        self, endpoint_client: AsyncClient
    ) -> None:
        """No users at all is seven days of zeros, not an empty list.

        Args:
            endpoint_client: an ASGI client served from this test's session.

        Returns:
            None.
        """
        response = await endpoint_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        entries = _entries(response)
        assert len(entries) == WINDOW_DAYS
        assert [entry["count"] for entry in entries] == [0] * WINDOW_DAYS

    async def test_a_window_with_no_creations_answers_seven_zero_counts(
        self, endpoint_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Users that exist outside the window leave every reported day at zero.

        Args:
            endpoint_client: an ASGI client served from this test's session.
            db_session: the per-test database session.

        Returns:
            None.
        """
        today = date.today()
        await _create_user_created_on(
            db_session, "ten-days-ago@example.com", today - timedelta(days=10)
        )
        await _create_user_created_on(
            db_session, "tomorrow@example.com", today + timedelta(days=1)
        )

        counts = _counts_by_day(await endpoint_client.get(ENDPOINT))

        assert len(counts) == WINDOW_DAYS
        assert set(counts.values()) == {0}

    async def test_a_quiet_day_reads_zero_rather_than_going_missing(
        self, endpoint_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """A day nobody was created on is a zero entry, not a gap in the list.

        Args:
            endpoint_client: an ASGI client served from this test's session.
            db_session: the per-test database session.

        Returns:
            None.
        """
        today = date.today()
        for index in range(2):
            await _create_user_created_on(
                db_session, f"today-{index}@example.com", today
            )
        await _create_user_created_on(
            db_session, "five-days-ago@example.com", today - timedelta(days=5)
        )

        response = await endpoint_client.get(ENDPOINT)

        assert _days_of(response) == _window()
        expected = [0, 1, 0, 0, 0, 0, 2]
        assert [entry["count"] for entry in _entries(response)] == expected


class TestCurrentDayIsIncluded:
    """AC-006: the current day is in the response even when it is incomplete."""

    async def test_the_current_day_is_the_last_entry(
        self, endpoint_client: AsyncClient
    ) -> None:
        """Today closes the window, whatever time of day this run happens at.

        Args:
            endpoint_client: an ASGI client served from this test's session.

        Returns:
            None.
        """
        today = date.today()

        days = _days_of(await endpoint_client.get(ENDPOINT))

        assert days[-1] == today
        assert today in days

    async def test_the_current_day_counts_the_users_created_so_far_today(
        self, endpoint_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """The incomplete day's count covers every creation that has happened.

        One user is stamped at the first moment of today and one at this instant,
        so both are unambiguously already created however late or early the suite
        runs: the day is reported with what it holds so far, not cut off earlier.

        Args:
            endpoint_client: an ASGI client served from this test's session.
            db_session: the per-test database session.

        Returns:
            None.
        """
        today = date.today()
        midnight = datetime(today.year, today.month, today.day, 0, 0, 0)
        await _create_user_created_at(db_session, "first-thing@example.com", midnight)
        await _create_user_created_at(
            db_session, "just-now@example.com", datetime.now()
        )

        response = await endpoint_client.get(ENDPOINT)

        counts = _counts_by_day(response)
        assert counts[today] == 2
        assert sum(counts.values()) == 2

    async def test_the_current_day_count_grows_as_the_day_goes_on(
        self, endpoint_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """A second creation today moves today's count: the day is live, not fixed.

        Args:
            endpoint_client: an ASGI client served from this test's session.
            db_session: the per-test database session.

        Returns:
            None.
        """
        today = date.today()
        await _create_user_created_on(db_session, "one@example.com", today, hour=9)

        assert _counts_by_day(await endpoint_client.get(ENDPOINT))[today] == 1

        await _create_user_created_on(db_session, "two@example.com", today, hour=10)

        assert _counts_by_day(await endpoint_client.get(ENDPOINT))[today] == 2

    async def test_the_current_day_is_reported_alongside_a_full_history(
        self, endpoint_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """A window filled on every day still ends with the current day.

        Args:
            endpoint_client: an ASGI client served from this test's session.
            db_session: the per-test database session.

        Returns:
            None.
        """
        for day in _window():
            await _create_user_created_on(
                db_session, f"every-day-{day.isoformat()}@example.com", day
            )

        response = await endpoint_client.get(ENDPOINT)

        assert _days_of(response) == _window()
        assert [entry["count"] for entry in _entries(response)] == [1] * WINDOW_DAYS


class TestBodyIsJsonArray:
    """AC-007: the response body is a JSON array of {date, count} entries."""

    async def test_the_body_is_json(self, endpoint_client: AsyncClient) -> None:
        """The response says JSON, so a consumer can parse it as JSON.

        Args:
            endpoint_client: an ASGI client served from this test's session.

        Returns:
            None.
        """
        response = await endpoint_client.get(ENDPOINT)

        assert response.headers["content-type"].startswith("application/json")

    async def test_the_body_is_an_array_of_objects(
        self, endpoint_client: AsyncClient
    ) -> None:
        """The top level is an array, not an object wrapping one.

        Args:
            endpoint_client: an ASGI client served from this test's session.

        Returns:
            None.
        """
        response = await endpoint_client.get(ENDPOINT)

        body = response.json()
        assert isinstance(body, list), f"the top level must be a JSON array: {body!r}"
        assert all(isinstance(entry, dict) for entry in body)

    async def test_every_entry_carries_a_date_and_a_non_negative_count(
        self, endpoint_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Each entry is a (date, count) pair with a parseable day and a count.

        Args:
            endpoint_client: an ASGI client served from this test's session.
            db_session: the per-test database session.

        Returns:
            None.
        """
        await _create_user_created_on(
            db_session, "entry-shape@example.com", date.today()
        )

        for entry in _entries(await endpoint_client.get(ENDPOINT)):
            assert date.fromisoformat(str(entry["date"]))
            assert entry["count"] >= 0
