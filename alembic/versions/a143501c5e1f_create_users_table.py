"""create users table

Revision ID: a143501c5e1f
Revises:
Create Date: 2026-02-27 09:27:42.811231

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a143501c5e1f"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    # Create index on email column
    op.create_index("ix_users_email", "users", ["email"], unique=False)


def downgrade() -> None:
    # Drop the index on email column
    op.drop_index("ix_users_email", table_name="users")
    # Drop users table
    op.drop_table("users")
