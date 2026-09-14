"""add an index on users.created_at for the daily-count analytics

GET /users/created-per-day (FEAT-6F3D) counts users grouped by the day of
users.created_at over a rolling seven-day window. The storage decision for
that feature (tasks/backlog/user-analytics/IMPLEMENTATION-GUIDE.md) is to
answer it from the existing users table rather than a separate analytics
table, so the only schema the analytics need is an index on the column the
query filters and groups on — without it every request scans the whole table.

Revision ID: 6f3d_add_created_at_index
Revises: 39f6add_domain_column
Create Date: 2026-09-14 22:45:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6f3d_add_created_at_index"
down_revision: str | None = "39f6add_domain_column"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Matches the ix_%(column_0_label)s naming convention declared in src/db/base.py,
# so the ORM model and the schema agree on the index name.
INDEX_NAME = "ix_users_created_at"


def upgrade() -> None:
    """Add the index the daily user-count aggregation runs on.

    The index is non-unique: many users share a creation instant, and the
    analytics group by day, not by an exact timestamp.
    """
    op.create_index(INDEX_NAME, "users", ["created_at"], unique=False)


def downgrade() -> None:
    """Remove the analytics index, leaving the users table itself untouched."""
    op.drop_index(INDEX_NAME, table_name="users")
