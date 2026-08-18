"""Tests for derived field calculations in user summaries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from src.users.calculations import calculate_days_since_created


class TestCalculateDaysSinceCreated:
    """Tests for the days_since_created calculation."""

    def test_returns_zero_for_today(self) -> None:
        """Test that a user created today returns 0 days."""
        today = datetime.now(UTC)
        result = calculate_days_since_created(today)
        assert result == 0
        assert isinstance(result, int)

    def test_returns_positive_for_past_date(self) -> None:
        """Test that a past creation date returns positive days."""
        past_date = datetime.now(UTC) - timedelta(days=30)
        result = calculate_days_since_created(past_date)
        assert result == 30
        assert isinstance(result, int)

    def test_handles_timezone_aware_dates(self) -> None:
        """Test that timezone-aware dates are handled correctly."""
        # Create a date with a non-UTC timezone
        tz_plus_5 = timezone(timedelta(hours=5))
        aware_date = datetime(2024, 1, 1, 12, 0, 0, tzinfo=tz_plus_5)
        result = calculate_days_since_created(aware_date)
        # Should convert to UTC first, then calculate days
        assert isinstance(result, int)
        assert result >= 0

    def test_handles_timezone_naive_dates(self) -> None:
        """Test that timezone-naive dates are handled correctly."""
        naive_date = datetime(2024, 1, 1, 12, 0, 0)
        result = calculate_days_since_created(naive_date)
        assert isinstance(result, int)
        assert result >= 0

    def test_returns_non_negative(self) -> None:
        """Test that the result is always non-negative."""
        future_date = datetime.now(UTC) + timedelta(days=100)
        result = calculate_days_since_created(future_date)
        assert result >= 0

    def test_exact_day_boundary(self) -> None:
        """Test calculation at exact day boundaries."""
        yesterday = datetime.now(UTC) - timedelta(days=1)
        result = calculate_days_since_created(yesterday)
        assert result == 1

    def test_large_past_date(self) -> None:
        """Test with a date far in the past."""
        old_date = datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)
        result = calculate_days_since_created(old_date)
        assert result > 0
        assert isinstance(result, int)
