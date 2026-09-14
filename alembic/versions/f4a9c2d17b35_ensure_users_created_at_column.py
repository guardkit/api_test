"""ensure the users created_at creation timestamp column

FEAT-3560 groups creations by day, so users.created_at is the column the whole
feature reads. Nothing in the chain has ever *asserted* it. a143501c5e1f creates
the column but with no server default - 3df3d0abd941 had to patch that up after
POST /users started dying on IntegrityError - and a database that reached the
head through a partial upgrade, a hand-edited schema, or a table rebuilt outside
alembic can arrive with the creation timestamp absent, nullable, or nullable with
NULLs in the older rows. Either way GET /users/created-per-day has nothing to
group on and POST /users can fail on the way in.

This revision guarantees users.created_at in the shape the model declares
(src/users/models.py: DateTime, NOT NULL, server_default=func.now()). It reads
the live schema and emits only the difference: the column is added where it is
absent, backfilled and tightened where it drifted, and left untouched where it
already matches, which is what makes the revision safe to re-run. Repairs go
through batch_alter_table because SQLite has no ALTER COLUMN SET DEFAULT / SET
NOT NULL and needs the table recreated to get either.

Downgrading restores the shape revision 39f6add_domain_column left behind, which
for this column is the same shape: 39f6add_domain_column already contains
created_at, created by a143501c5e1f and defaulted by 3df3d0abd941. Dropping the
column on the way down would land the database in a state the chain never had -
and 3df3d0abd941's own downgrade alters that column, so a blind drop would raise
KeyError part way through `alembic downgrade base`.

Revision ID: f4a9c2d17b35
Revises: 39f6add_domain_column
Create Date: 2026-09-14 12:41:07.000000

"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4a9c2d17b35"
down_revision: str | None = "39f6add_domain_column"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "users"
_COLUMN = "created_at"


def _live_columns(direction: str) -> dict[str, Any]:
    """Reflect the users table and return its columns keyed by name.

    Args:
        direction: "upgrade" or "downgrade", so a failure names the move that
            was being attempted.

    Returns:
        dict[str, Any]: Column dictionaries from SQLAlchemy reflection, keyed by
        name; each carries at least "nullable" and "default".

    Raises:
        RuntimeError: If the users table is missing, which means the chain was
            never run against this database rather than migrated to this point.
    """
    inspector: sa.Inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(_TABLE):
        raise RuntimeError(
            f"the {direction} of revision {revision} cannot continue: table "
            f"{_TABLE!r} does not exist in this database, so the chain was never "
            f"run here; the table is created by revision a143501c5e1f"
        )
    return {str(column["name"]): column for column in inspector.get_columns(_TABLE)}


def _guarantee_created_at(direction: str) -> None:
    """Put users.created_at into DateTime NOT NULL DEFAULT CURRENT_TIMESTAMP.

    Emits only what the live schema is missing, so a database that already
    matches gets no DDL at all.

    Args:
        direction: "upgrade" or "downgrade", used to say which way the revision
            was moving when the users table turns out to be missing.
    """
    column = _live_columns(direction).get(_COLUMN)

    if column is None:
        # Absent. SQLite refuses ADD COLUMN with a non-constant default, so the
        # column goes in loose - nullable, no default - and is backfilled and
        # tightened to the declared shape below, which every engine can do.
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.DateTime(), nullable=True))
        has_server_default = False
        is_nullable = True
    else:
        has_server_default = column.get("default") is not None
        is_nullable = bool(column.get("nullable", False))

    if has_server_default and not is_nullable:
        # Already the declared shape - emit nothing.
        return

    if is_nullable:
        # Rows written while the column was nullable hold NULL, and NOT NULL is
        # unreachable until they have a timestamp. CURRENT_TIMESTAMP is the
        # value the server default would have given them at insert time.
        op.execute(
            sa.text(
                f"UPDATE {_TABLE} SET {_COLUMN} = CURRENT_TIMESTAMP "
                f"WHERE {_COLUMN} IS NULL"
            )
        )

    # batch_alter_table: SQLite cannot set a default or nullability in place, so
    # batch mode recreates the table and carries the rows and indexes across.
    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.alter_column(
            _COLUMN,
            existing_type=sa.DateTime(),
            existing_nullable=is_nullable,
            nullable=False,
            server_default=sa.func.now(),
        )


def upgrade() -> None:
    """Guarantee users.created_at, creating or repairing it as the schema needs.

    Three states are possible and each is handled: the column is absent, so it
    is added and then given the declared shape; it drifted to nullable, or lost
    its server default, so its NULL rows are backfilled and it is tightened back
    up; or it already matches, in which case nothing is emitted and re-running
    the revision stays harmless.
    """
    _guarantee_created_at("upgrade")


def downgrade() -> None:
    """Restore users.created_at to the shape held one revision back.

    The revision below this one already carries the creation timestamp, so the
    state being returned to is a DateTime NOT NULL column with the
    CURRENT_TIMESTAMP default: an empty database, or one whose column was added
    by this revision, gets it recreated in exactly that shape, and one that
    drifted while at this revision is put back the same way.
    """
    _guarantee_created_at("downgrade")
