"""SQLAlchemy models backing user-creation analytics.

Every data point of the daily series is a count of ``users`` rows grouped by
the day of ``users.created_at``. The storage decision recorded for FEAT-6F3D
(tasks/backlog/user-analytics/IMPLEMENTATION-GUIDE.md) is to answer the
analytics from the existing ``users`` table with an index on ``created_at``,
so this bounded context adds no table of its own and the ORM model its
queries are written against is :class:`src.users.models.User`.

This module names that model and the column the daily aggregation groups on,
so consumers inside the analytics context import one thing instead of
reaching into the users module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from src.users.models import User

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.orm import InstrumentedAttribute

UserAnalyticsSource: Final[type[User]] = User
"""The ORM model every analytics query in this package is written against."""

# The instrumented column of the users table: what a query filters and groups
# on, rather than the datetime a row of the table carries.
ANALYTICS_TIMESTAMP_COLUMN: Final[InstrumentedAttribute[datetime]] = User.created_at
"""The column the daily counts are filtered by and grouped on."""

__all__ = ["ANALYTICS_TIMESTAMP_COLUMN", "UserAnalyticsSource"]
