"""Derived field calculations for user summaries and creation analytics."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta


def calculate_days_since_created(created_at: datetime) -> int:
    """Calculate the number of days between a creation date and today.

    Handles both timezone-aware and timezone-naive datetimes correctly.
    Timezone-aware datetimes are converted to UTC before extracting the date.

    Args:
        created_at: The creation datetime (timezone-aware or naive).

    Returns:
        The number of days since creation as a non-negative integer.
    """
    if created_at.tzinfo is not None:
        utc_date = created_at.astimezone(UTC).date()
    else:
        utc_date = created_at.date()

    today = date.today()
    delta = (today - utc_date).days
    return max(delta, 0)


def recent_creation_window_end(today: date | None = None) -> date:
    """Return the newest day the creation-per-day analytics answers for.

    The analytics answer for the recent window of whole days, and today is a day
    still in progress, so today is not answered for: the newest day of the window
    is the day before it, and the window runs back from there.

    Args:
        today: The day to count from, defaulting to today. Name it to describe a
            window relative to another day.

    Returns:
        date: The day before ``today``.
    """
    return (date.today() if today is None else today) - timedelta(days=1)
