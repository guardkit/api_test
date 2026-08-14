"""add missing server defaults to users timestamps

Corrective migration (pilot's second real find, adjudicated by Rich 08-14):
a143501c5e1f created users.created_at / users.updated_at NOT NULL with NO
server default, while the model (src/users/models.py) declares
server_default=func.now() on both. On an alembic-built database every
POST /users therefore died on IntegrityError — misreported as 409
"already exists". Databases built via metadata create_all never showed it.
This migration brings the schema to what the model always declared:
DEFAULT CURRENT_TIMESTAMP on both columns (batch_alter_table so SQLite
table-recreate semantics work; a no-op rewrite on engines with native
ALTER COLUMN SET DEFAULT).

Revision ID: 3df3d0abd941
Revises: a143501c5e1f
Create Date: 2026-08-14 23:26:51.211872

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3df3d0abd941'
down_revision: Union[str, None] = 'a143501c5e1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Match the model: server_default=func.now() on both timestamp columns.
    # batch_alter_table -> SQLite recreates the table (the only way it can
    # add a column default); existing rows and data are preserved.
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            existing_nullable=False,
            server_default=sa.func.now(),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            existing_nullable=False,
            server_default=sa.func.now(),
        )


def downgrade() -> None:
    # Back to a143501c5e1f's (defective) shape: NOT NULL, no default.
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            existing_nullable=False,
            server_default=None,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            existing_nullable=False,
            server_default=None,
        )
