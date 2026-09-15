"""User-creation analytics: daily counts over the existing users table.

The storage decision recorded for FEAT-6F3D
(tasks/backlog/user-analytics/IMPLEMENTATION-GUIDE.md, "Storage approach") is to
answer the daily series from the ``users`` table with an index on
``users.created_at``; the schema change that carries is
``alembic/versions/6f3d_add_created_at_index_to_users.py``. Analytics writes no
rows and owns no table.

That decides two things about the shape of this package:

* It declares no ``models.py``. ADR-001 requires that file "only where the
  feature stores data in the database", and the table the daily counts read
  belongs to ``src.users``, which declares it in ``src/users/models.py``.
* Its query layer reaches user data through the users feature's public read
  interface — ``src.users.crud`` and ``src.users.schemas`` — and never through
  ``src.users.models`` or any other private file (ADR-001, amendment of
  2026-08-31). ``tests/analytics/test_created_per_day_schemas.py`` enforces
  that boundary, so it cannot regress silently.
"""

from src.analytics.schemas import (
    CreatedPerDayResponse,
    UserCount,
    UserCountByDate,
)

__all__ = [
    "CreatedPerDayResponse",
    "UserCount",
    "UserCountByDate",
]
