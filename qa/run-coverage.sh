#!/usr/bin/env bash
# The coverage measurement of record for api_test (.guardkit/config.yaml,
# toolchain.coverage). The factory's Coach runs this itself, after its own
# independent test run, when a task's type requires coverage: exit 0 means the
# project's stated minimum line coverage (.claude/CLAUDE.md: 80%) is met.
#
# It measures; it does not judge the tests. The verdict on the tests is
# qa/run-suite.sh's (forked, against Postgres). Coverage cannot be collected
# from forked test processes (measured 2026-09-19: 48% forked vs 95% in-process
# on the same tree), so this runs the suite in-process on the unit-test
# database and takes ONLY the coverage report's exit code as its own.
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${PWD}/.venv/bin/python"
[[ -x "$PY" ]] || { echo "qa/run-coverage.sh: no interpreter at ${PY} — the work leg's bootstrap makes it" >&2; exit 2; }
"$PY" -c "import coverage" >/dev/null 2>&1 || "$PY" -m pip install -q -e ".[dev]" >/dev/null 2>&1 || { echo "qa/run-coverage.sh: could not install the test extras (.[dev])" >&2; exit 2; }
COVERAGE_FILE="$(mktemp -t api-test-coverage.XXXXXX)"
export COVERAGE_FILE
trap 'rm -f "$COVERAGE_FILE"' EXIT
MINIMUM="${API_TEST_MIN_LINE_COVERAGE:-80}"
# Test failures do not decide this script; a run that collected nothing does.
"$PY" -m coverage run --source=src -m pytest -q -p no:cacheprovider >/dev/null 2>&1
"$PY" -m coverage report --fail-under="$MINIMUM" | tail -4
exit "${PIPESTATUS[0]}"
