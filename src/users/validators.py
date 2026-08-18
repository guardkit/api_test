"""Validation utilities for users module."""

from __future__ import annotations

MAX_LIMIT = 100


def validate_limit(limit_str: str) -> int:
    """Validate and parse a limit query parameter.

    Args:
        limit_str: The limit value as a string from the query parameter.

    Returns:
        The validated limit as an integer.

    Raises:
        ValueError: If the limit is not a positive integer or exceeds MAX_LIMIT.
    """
    try:
        limit = int(limit_str)
    except (ValueError, TypeError):
        raise ValueError("limit must be a positive integer") from None

    if limit <= 0:
        raise ValueError("limit must be a positive integer")

    if limit > MAX_LIMIT:
        raise ValueError(f"limit must not exceed {MAX_LIMIT}")

    return limit
