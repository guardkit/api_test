"""Tests for the users.created_at migration (TASK-3560-003).

Every test drives the real revision in ``alembic/versions`` with the alembic
CLI against its own throwaway SQLite file, so what gets asserted is the schema
the migration actually leaves behind, not the text of the migration file:

* AC-001 - the revision puts ``users.created_at`` in place as a DateTime, NOT
  NULL, with a server default: created when absent, repaired when drifted,
  left alone when it already matches.
* AC-002 - the revision moves down to the previous revision's state and back up
  again, with the rows intact, and the whole chain still round-trips to base.
* AC-003 - ``alembic check`` reports no drift at head.

The ambient ``DATABASE_URL`` is overridden on purpose: these tests are about the
migration, so they run against a database of their own rather than whichever one
the rest of the suite happens to use.
"""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy import Engine, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSIONS_DIR = PROJECT_ROOT / "alembic" / "versions"
TABLE = "users"
COLUMN = "created_at"

# What the fixture hands each test: the async URL alembic is pointed at, a sync
# engine over the same file, this revision's id, and its parent's id.
MigratedDb = tuple[str, Engine, str, str]

# The users table as it stands one revision below this migration, with a
# created_at that drifted: nullable, and with no server default. It proves the
# repair path is real rather than a no-op.
DRIFTED_USERS_TABLE = """
CREATE TABLE users (
    id VARCHAR NOT NULL,
    email VARCHAR NOT NULL,
    full_name VARCHAR,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME,
    domain VARCHAR,
    CONSTRAINT pk_users PRIMARY KEY (id),
    CONSTRAINT uq_users_email UNIQUE (email)
)
"""


def _migration_file() -> Path:
    """Return the revision file that owns the created_at column.

    Returns:
        Path: The migration named for created_at.

    Raises:
        AssertionError: If no such migration exists.
    """
    files = sorted(
        f for f in VERSIONS_DIR.glob("*.py") if "created_at" in f.name.lower()
    )
    assert files, "a migration for the created_at column should exist"
    return files[0]


def _declared_revision(module_text: str, name: str) -> str:
    """Read a revision identifier ('revision' or 'down_revision') from a module.

    Args:
        module_text: Source of the migration file.
        name: Which identifier to read out of it.

    Returns:
        str: The declared revision string.

    Raises:
        AssertionError: If the migration does not declare it as a plain string.
    """
    match = re.search(rf"^{name}[^\n=]*=\s*(.+)$", module_text, re.MULTILINE)
    assert match is not None, f"{name} is not declared by the created_at migration"
    value: object = ast.literal_eval(match.group(1))
    assert isinstance(value, str), f"{name} should be a string, got {value!r}"
    return value


def _alembic(database_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the alembic CLI against ``database_url`` and insist it succeeded.

    The CLI is taken from next to the running interpreter so the tests do not
    depend on the virtualenv being on PATH.

    Args:
        database_url: Async SQLAlchemy URL the migration runs against.
        *args: Alembic subcommand and its arguments, e.g. ("upgrade", "head").

    Returns:
        subprocess.CompletedProcess[str]: The finished run.

    Raises:
        AssertionError: If alembic exited non-zero.
    """
    sibling = Path(sys.executable).with_name("alembic")
    cli = [str(sibling)] if sibling.exists() else [shutil.which("alembic") or "alembic"]
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    result = subprocess.run(
        [*cli, *args],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert result.returncode == 0, (
        f"`alembic {' '.join(args)}` exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return result


def _head_lines(reported: str) -> list[str]:
    """Return the head revisions alembic reported, one per line."""
    return [line.strip() for line in reported.splitlines() if line.strip()]


def _scalar(engine: Engine, statement: str) -> Any:
    """Run a one-value SELECT and return it."""
    with engine.begin() as connection:
        return connection.execute(text(statement)).scalar_one()


def _column_state(engine: Engine) -> dict[str, Any] | None:
    """Reflect users.created_at.

    Args:
        engine: Sync engine over the database under test.

    Returns:
        dict[str, Any] | None: The reflected column, or None when the table or
        the column is not there.
    """
    inspector = sa.inspect(engine)
    if not inspector.has_table(TABLE):
        return None
    for column in inspector.get_columns(TABLE):
        if str(column["name"]) == COLUMN:
            return dict(column)
    return None


def _column_names(engine: Engine) -> list[str]:
    """Return the users table's column names, or [] when it is absent."""
    inspector = sa.inspect(engine)
    if not inspector.has_table(TABLE):
        return []
    return [str(column["name"]) for column in inspector.get_columns(TABLE)]


def _row_count(engine: Engine) -> int:
    """Return how many rows the users table holds."""
    return int(_scalar(engine, f"SELECT COUNT(*) FROM {TABLE}"))


def _null_created_at_count(engine: Engine) -> int:
    """Return how many rows are missing a creation timestamp."""
    where = f"SELECT COUNT(*) FROM {TABLE} WHERE {COLUMN} IS NULL"
    return int(_scalar(engine, where))


def _stored_created_at(engine: Engine, email: str) -> Any:
    """Return the creation timestamp stored for one user."""
    return _scalar(engine, f"SELECT {COLUMN} FROM {TABLE} WHERE email = '{email}'")


def _insert_user(engine: Engine, email: str, created_at: str | None) -> None:
    """Add a user, leaving created_at out of the INSERT when it is None.

    Args:
        engine: Sync engine over the database under test.
        email: Address for the new user.
        created_at: Literal timestamp, or None to name the column in no part of
            the statement and let the server answer for it (or, on a drifted
            table, to leave the row without one).
    """
    columns = [
        "id",
        "email",
        "full_name",
        "is_active",
        "updated_at",
        "deleted_at",
        "domain",
    ]
    values = [
        f"lower('{email}')",
        f"'{email}'",
        "'Test User'",
        "1",
        "CURRENT_TIMESTAMP",
    ]
    values += ["NULL", "NULL"]
    if created_at is not None:
        columns.insert(4, COLUMN)
        values.insert(4, f"'{created_at}'")
    statement = text(
        f"INSERT INTO {TABLE} ({', '.join(columns)}) VALUES ({', '.join(values)})"
    )
    with engine.begin() as connection:
        connection.execute(statement)


def _drop_created_at(engine: Engine) -> None:
    """Take the column away by hand, simulating a database that drifted."""
    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {TABLE} DROP COLUMN {COLUMN}"))


@pytest.fixture()
def migrated_db(tmp_path: Path) -> Iterator[MigratedDb]:
    """Provide a throwaway file database plus this migration's revision ids."""
    path = tmp_path / "created_at_migration.db"
    source = _migration_file().read_text()
    yield (
        f"sqlite+aiosqlite:///{path}",
        sa.create_engine(f"sqlite:///{path}"),
        _declared_revision(source, "revision"),
        _declared_revision(source, "down_revision"),
    )


def test_created_at_revision_is_the_single_head(tmp_path: Path) -> None:
    """The new revision extends the chain rather than forking it."""
    source = _migration_file().read_text()
    revision = _declared_revision(source, "revision")
    previous = _declared_revision(source, "down_revision")
    assert revision != previous, "a revision cannot revise itself"

    probe = f"sqlite+aiosqlite:///{tmp_path / 'head_probe.db'}"
    heads = _head_lines(_alembic(probe, "heads").stdout)
    assert len(heads) == 1, f"there should be one head, got: {heads}"
    assert revision in heads[0], f"the head should be {revision}, got: {heads[0]}"
    assert previous in source, "the revision should name the head it follows"


def test_upgrade_creates_created_at_when_it_is_missing(migrated_db: MigratedDb) -> None:
    """AC-001: the revision creates the column in the shape the model declares."""
    url, engine, _, previous = migrated_db
    _alembic(url, "upgrade", "head")
    _drop_created_at(engine)
    assert _column_state(engine) is None, "the column should be gone before the upgrade"

    _alembic(url, "stamp", previous)
    _alembic(url, "upgrade", "head")

    column = _column_state(engine)
    assert column is not None, "upgrade should have created users.created_at"
    assert isinstance(column["type"], sa.DateTime), (
        f"should be DateTime, is {column['type']}"
    )
    assert column["nullable"] is False, "created_at should be NOT NULL"
    assert column["default"] is not None, "created_at should carry a server default"


def test_server_default_stamps_new_rows(migrated_db: MigratedDb) -> None:
    """A row written without a timestamp still gets one."""
    url, engine, _, previous = migrated_db
    _alembic(url, "upgrade", "head")
    _drop_created_at(engine)
    _alembic(url, "stamp", previous)
    _alembic(url, "upgrade", "head")

    _insert_user(engine, "defaulted@example.test", None)

    stored = _stored_created_at(engine, "defaulted@example.test")
    assert stored is not None, "the server default should have filled created_at"


def test_upgrade_repairs_a_drifted_column(migrated_db: MigratedDb) -> None:
    """A nullable created_at with NULL rows is backfilled and made NOT NULL."""
    url, engine, _, previous = migrated_db
    with engine.begin() as connection:
        connection.execute(text(DRIFTED_USERS_TABLE))
    _insert_user(engine, "kept@example.test", "2026-01-02 03:04:05")
    _insert_user(engine, "untimestamped@example.test", None)
    assert _null_created_at_count(engine) == 1, "the drifted table should start adrift"

    _alembic(url, "stamp", previous)
    _alembic(url, "upgrade", "head")

    column = _column_state(engine)
    assert column is not None, "upgrade should have repaired users.created_at"
    assert column["nullable"] is False, "a drifted created_at should end up NOT NULL"
    assert column["default"] is not None, "a drifted created_at needs a server default"
    assert _null_created_at_count(engine) == 0, "NULL timestamps should be backfilled"
    kept = _stored_created_at(engine, "kept@example.test")
    assert str(kept).startswith("2026-01-02 03:04:05"), (
        f"timestamps must survive: {kept!r}"
    )
    assert _row_count(engine) == 2, "the repair must not lose rows"


def test_upgrade_is_a_no_op_on_a_healthy_database(migrated_db: MigratedDb) -> None:
    """Re-running the revision over a matching schema changes nothing."""
    url, engine, _, previous = migrated_db
    _alembic(url, "upgrade", "head")
    _insert_user(engine, "steady@example.test", None)
    before = _column_state(engine)
    names_before = _column_names(engine)
    stored_before = _stored_created_at(engine, "steady@example.test")
    assert before is not None

    _alembic(url, "stamp", previous)
    _alembic(url, "upgrade", "head")

    after = _column_state(engine)
    assert after is not None
    assert after["nullable"] == before["nullable"], (
        "a healthy column must not be rewritten"
    )
    assert after["default"] == before["default"], (
        "a healthy default must not be rewritten"
    )
    assert _column_names(engine) == names_before, "no column should come or go"
    assert _stored_created_at(engine, "steady@example.test") == stored_before
    assert _row_count(engine) == 1


def test_revision_is_reversible(migrated_db: MigratedDb) -> None:
    """AC-002: the revision steps down to the previous state and back up."""
    url, engine, revision, previous = migrated_db
    _alembic(url, "upgrade", "head")
    _insert_user(engine, "reversible@example.test", None)
    names = _column_names(engine)

    _alembic(url, "downgrade", previous)
    assert previous in _alembic(url, "current").stdout, (
        "the database should sit at the parent"
    )
    column = _column_state(engine)
    assert column is not None, "the parent revision's users table has a created_at"
    assert column["nullable"] is False, "downgrade leaves the shape the parent had"
    assert column["default"] is not None, "downgrade leaves the parent's server default"
    assert _column_names(engine) == names, (
        "no column comes or goes across the downgrade"
    )
    assert _null_created_at_count(engine) == 0, "rows keep their timestamps"

    _alembic(url, "upgrade", "head")
    assert revision in _alembic(url, "current").stdout, (
        "the database should sit at head"
    )
    assert _stored_created_at(engine, "reversible@example.test") is not None


def test_downgrade_recreates_a_column_that_was_lost(migrated_db: MigratedDb) -> None:
    """AC-002: stepping down over a database missing the column puts it back."""
    url, engine, _, previous = migrated_db
    _alembic(url, "upgrade", "head")
    _insert_user(engine, "regained@example.test", None)
    _drop_created_at(engine)
    assert _column_state(engine) is None

    _alembic(url, "downgrade", previous)

    column = _column_state(engine)
    assert column is not None, "downgrade should restore users.created_at"
    assert column["nullable"] is False
    assert column["default"] is not None
    assert _null_created_at_count(engine) == 0, "surviving rows are given a timestamp"


def test_full_chain_round_trip_keeps_the_column(migrated_db: MigratedDb) -> None:
    """AC-002: the chain still round-trips to base and back through this revision."""
    url, engine, revision, _ = migrated_db
    _alembic(url, "upgrade", "head")
    _alembic(url, "downgrade", "base")
    assert _column_names(engine) == [], "downgrade base should leave no users table"

    _alembic(url, "upgrade", "head")
    assert revision in _alembic(url, "current").stdout
    column = _column_state(engine)
    assert column is not None, "the round trip should leave users.created_at in place"
    assert column["nullable"] is False
    assert column["default"] is not None


def test_alembic_check_reports_no_drift(migrated_db: MigratedDb) -> None:
    """AC-003: the chain at head matches the ORM metadata."""
    url, _engine, _, _ = migrated_db
    _alembic(url, "upgrade", "head")
    output = _alembic(url, "check").stdout
    assert "No new upgrade operations detected" in output, (
        f"alembic check said: {output}"
    )
