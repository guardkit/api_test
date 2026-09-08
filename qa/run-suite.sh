#!/usr/bin/env bash
# The suite of record for api_test (qa/known-failures.yaml): the forked pytest
# run against a Postgres, which is where this app's real defects live (the
# SQLite the unit tests use forgives what Postgres refuses). It is the test
# command the factory's merge-ready checks run (.guardkit/config.yaml,
# toolchain.test), inside the repository's Docker Sandbox, so it brings its own
# throwaway Postgres up in whatever Docker engine it runs in and tears it down
# after. Exit code = verdict.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PWD}/.venv/bin/python"
[[ -x "$PY" ]] || { echo "qa/run-suite.sh: no interpreter at ${PY} — the work leg's bootstrap makes it" >&2; exit 2; }
NAME="api-test-suite-pg-$$"
PORT="${SUITE_PG_PORT:-5433}"
docker run -d --rm --name "$NAME" -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test -p "127.0.0.1:${PORT}:5432" postgres:16-alpine >/dev/null
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT
for _ in $(seq 1 60); do docker exec "$NAME" pg_isready -U postgres >/dev/null 2>&1 && break; sleep 1; done
export DATABASE_URL="postgresql+asyncpg://postgres:test@localhost:${PORT}/test"
export PATH="${PWD}/.venv/bin:${PATH}"
# Every deselected test below is ledgered in qa/known-failures.yaml with its
# reason (a stale migration test; two cross-test event-loop teardown artefacts
# that pass in isolation). Zero net-new failures against the ledger is the bar.
exec "$PY" -m pytest -q --forked -p no:cacheprovider \
  --deselect tests/test_alembic.py::test_users_table_migration_contains_columns \
  --deselect tests/test_middleware.py::TestMiddlewareIntegration::test_correlation_id_passed_through_response \
  --deselect tests/test_middleware.py::TestMiddlewareIntegration::test_multiple_requests_get_different_correlation_ids
