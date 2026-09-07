"""add deleted_at column to users table

Add a nullable deleted_at timestamp column to the users table to support
soft-delete operations. The column is nullable (allowing active users to
have NULL) and is of DateTime type (not a boolean).

Revision ID: 39f6add_deleted_at
Revises: 3df3d0abd941
Create Date: 2026-09-07 05:55:25.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "39f6add_deleted_at"
down_revision: str | None = "3df3d0abd941"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add deleted_at column to users table.

    The column is:
    - nullable (allows existing active users to have NULL)
    - DateTime type (supports soft-delete timestamps)
    """
    op.add_column(
        "users",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Remove deleted_at column from users table."""
    op.drop_column("users", "deleted_at")
