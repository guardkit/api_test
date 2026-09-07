"""add domain column to users table

The initial migration (a143501c5e1f) created the users table without the
domain column that the User model declares. This migration adds the missing
nullable domain column with an index to match the model definition.

Revision ID: 39f6add_domain_column
Revises: 39f6add_deleted_at
Create Date: 2026-09-07 07:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "39f6add_domain_column"
down_revision: str | None = "39f6add_deleted_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add domain column to users table.

    The column is:
    - nullable (allows existing users without domain)
    - indexed (matches the model's index=True)
    """
    op.add_column(
        "users",
        sa.Column("domain", sa.String(), nullable=True),
    )
    op.create_index("ix_users_domain", "users", ["domain"], unique=False)


def downgrade() -> None:
    """Remove domain column from users table."""
    op.drop_index("ix_users_domain", table_name="users")
    op.drop_column("users", "domain")
