#!/usr/bin/env bash
# THE WHOLE-FEATURE CHECK for api_test (.guardkit/config.yaml,
# toolchain.feature_check). The factory runs this once, after the last build
# wave, before a merge can be offered: every task may have passed its own
# tests and the thing the person asked for can still be wrong at the surface
# they use. This asks the feature's own question, over the wire, against the
# real app and a real Postgres.
#
# It knows nothing about any particular endpoint. Everything it proves comes
# from the feature record the factory hands it:
#
#   1. read the record named by GUARDKIT_FEATURE_RECORD and list its scenarios;
#   2. for every scenario stamped `verifier: hurl`, find its frozen twin by the
#      same rule guardkit's build-completion check uses (qa/feature_check_twins.py);
#   3. a stamped scenario with no twin is MISSING EVIDENCE — this check fails
#      and names it, and nothing is started;
#   4. otherwise start the candidate's own app against a throwaway Postgres and
#      run each twin with hurl, judging each scenario on its own result;
#   5. print a table, the failures a coder can act on, and one line of JSON
#      naming the scenarios whose twins passed.
#
# Exit 0 is the only pass. Absence never passes: no record, no scenarios, no
# twin, no app, no hurl — all of them fail loudly.
#
# What it leaves behind: nothing. One Postgres container named after the
# candidate and this process id, one app process, one mktemp directory; the
# trap removes exactly those and touches nothing else.
set -uo pipefail

ROOT="${GUARDKIT_WORKTREE:-}"
if [[ -z "$ROOT" || ! -d "$ROOT" ]]; then ROOT="$(cd "$(dirname "$0")/.." && pwd)"; fi
cd "$ROOT" || { echo "qa/feature-check.sh: could not enter ${ROOT}" >&2; exit 2; }

FEATURE_ID="${GUARDKIT_FEATURE_ID:-unknown-feature}"
RECORD="${GUARDKIT_FEATURE_RECORD:-}"
SHA="${GUARDKIT_CANDIDATE_SHA:-}"
if [[ -z "$SHA" ]]; then SHA="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"; fi
SHORT_SHA="${SHA:0:12}"

# The worktree's virtual environment cannot be assumed to exist: the factory's
# work legs bootstrap it from pyproject, and qa/run-suite.sh already treats a
# missing one as exit 2 with a plain sentence rather than a stack trace. Same
# here, and the same top-up of the declared extras, because a leg may have
# installed only the app.
PY="${ROOT}/.venv/bin/python"
[[ -x "$PY" ]] || { echo "qa/feature-check.sh: no interpreter at ${PY} — the work leg's bootstrap makes it" >&2; exit 2; }
if ! "$PY" -c "import yaml, uvicorn, alembic" >/dev/null 2>&1; then
  "$PY" -m pip install -q -e ".[dev]" >/dev/null 2>&1 || { echo "qa/feature-check.sh: could not install the app and its test extras (.[dev])" >&2; exit 2; }
fi
"$PY" -c "import yaml, uvicorn, alembic" >/dev/null 2>&1 || { echo "qa/feature-check.sh: the worktree venv still has no uvicorn/alembic/pyyaml after installing .[dev]" >&2; exit 2; }

HURL_BIN="${HURL_BIN:-$HOME/.local/bin/hurl}"
if [[ ! -x "$HURL_BIN" ]]; then HURL_BIN="$(command -v hurl 2>/dev/null || true)"; fi
[[ -n "$HURL_BIN" && -x "$HURL_BIN" ]] || { echo "qa/feature-check.sh: no hurl runner found (looked at \$HURL_BIN, \$HOME/.local/bin/hurl and the PATH) — the frozen twins cannot be run" >&2; exit 2; }

HELPER="${ROOT}/qa/feature_check_twins.py"
[[ -f "$HELPER" ]] || { echo "qa/feature-check.sh: its own helper ${HELPER} is missing" >&2; exit 2; }

RUNDIR="$(mktemp -d -t api-test-feature-check-XXXXXX)"
PG_NAME="api-test-feature-check-${SHORT_SHA}-$$"
APP_PID=""
cleanup() {
  [[ -n "$APP_PID" ]] && kill "$APP_PID" >/dev/null 2>&1
  [[ -n "$APP_PID" ]] && wait "$APP_PID" 2>/dev/null
  docker rm -f "$PG_NAME" >/dev/null 2>&1
  rm -rf "$RUNDIR" >/dev/null 2>&1
  return 0
}
trap cleanup EXIT

echo "WHOLE-FEATURE CHECK — ${FEATURE_ID} at ${SHORT_SHA}"
echo "worktree: ${ROOT}"
echo "feature record: ${RECORD:-(none given)}"
echo

[[ -n "$RECORD" ]] || { echo "qa/feature-check.sh: GUARDKIT_FEATURE_RECORD is empty, so there is no feature record to read and nothing can be proved." >&2; exit 1; }

# ---------------------------------------------------------------- scenarios
SCENARIOS="${RUNDIR}/scenarios.tsv"
if ! "$PY" "$HELPER" scenarios "$RECORD" "$ROOT" >"$SCENARIOS" 2>"${RUNDIR}/scenarios.err"; then
  cat "${RUNDIR}/scenarios.err" >&2
  echo "qa/feature-check.sh: the feature's scenarios could not be read, so this check proves nothing and fails." >&2
  exit 1
fi

MISSING=()
TITLES=()
TWINS=()
OTHER_TITLES=()
OTHER_VERIFIERS=()
while IFS=$'\t' read -r kind title verifier twin; do
  [[ -z "${kind:-}" ]] && continue
  case "$kind" in
    hurl-twin)    TITLES+=("$title"); TWINS+=("$twin") ;;
    hurl-missing) MISSING+=("$title") ;;
    other)        OTHER_TITLES+=("$title"); OTHER_VERIFIERS+=("$verifier") ;;
  esac
done <"$SCENARIOS"

if (( ${#MISSING[@]} > 0 )); then
  echo "MISSING EVIDENCE — this feature promises scenarios it cannot prove."
  echo
  echo "These scenarios are stamped 'verifier: hurl' in the feature record, which"
  echo "means each one is proven over the wire by a frozen Hurl twin, and no twin"
  echo "file exists for them:"
  for title in "${MISSING[@]}"; do echo "  - ${title}"; done
  echo
  echo "Write one twin file per scenario above, under qa/twins/<feature-area>/,"
  echo "named for the scenario (for example qa/twins/time-endpoint/reading-current-server-time.hurl)."
  echo "Either point the scenario's stamp at it with"
  echo "    test_ref: qa/twins/<feature-area>/<file>.hurl"
  echo "or give the twin a comment line carrying the scenario title exactly:"
  echo "    # Scenario: <the scenario title, character for character>"
  echo "The twin addresses the app as {{base_url}} and may use {{run_marker}} for"
  echo "unique test data. No app was started: absence of evidence is a failure."
  exit 1
fi

if (( ${#TITLES[@]} == 0 )); then
  echo "NOTHING TO PROVE — the feature record names scenarios, but not one of them"
  echo "is stamped 'verifier: hurl', so this check has no way to exercise the"
  echo "feature at the surface a person uses. In this project a scenario proven"
  echo "over the wire carries that stamp and a frozen twin under qa/twins/."
  if (( ${#OTHER_TITLES[@]} > 0 )); then
    echo
    echo "The scenarios in the record and who they are routed to:"
    for i in "${!OTHER_TITLES[@]}"; do echo "  - ${OTHER_TITLES[$i]}  [verifier: ${OTHER_VERIFIERS[$i]}]"; done
  fi
  exit 1
fi

# ------------------------------------------------------- the real database
docker run -d --rm --name "$PG_NAME" \
  -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test \
  --tmpfs /var/lib/postgresql/data \
  -p "127.0.0.1:0:5432" postgres:16-alpine >/dev/null 2>"${RUNDIR}/pg.err"
if [[ $? -ne 0 ]]; then
  echo "qa/feature-check.sh: could not start the throwaway Postgres:" >&2
  tail -5 "${RUNDIR}/pg.err" >&2
  exit 2
fi
PG_PORT="$(docker port "$PG_NAME" 5432/tcp | head -1 | sed -E 's/.*:([0-9]+)$/\1/')"
[[ -n "$PG_PORT" ]] || { echo "qa/feature-check.sh: could not read the Postgres port" >&2; exit 2; }
PG_READY=""
for _ in $(seq 1 60); do
  docker exec "$PG_NAME" pg_isready -U postgres >/dev/null 2>&1 && { PG_READY=yes; break; }
  sleep 1
done
[[ -n "$PG_READY" ]] || { echo "qa/feature-check.sh: the throwaway Postgres never became ready" >&2; exit 2; }

export DATABASE_URL="postgresql+asyncpg://postgres:test@127.0.0.1:${PG_PORT}/test"
export PATH="${ROOT}/.venv/bin:${PATH}"

# The candidate's own migrations, exactly as the container entrypoint runs them.
ALEMBIC="${ROOT}/.venv/bin/alembic"
if [[ -x "$ALEMBIC" ]]; then "$ALEMBIC" upgrade head >"${RUNDIR}/alembic.log" 2>&1
else "$PY" -m alembic upgrade head >"${RUNDIR}/alembic.log" 2>&1; fi
if [[ $? -ne 0 ]]; then
  echo "qa/feature-check.sh: the candidate's migrations (alembic upgrade head) failed, so the app could not be started:" >&2
  tail -20 "${RUNDIR}/alembic.log" >&2
  exit 1
fi

# ------------------------------------------------------------- the real app
APP_PORT="$("$PY" "$HELPER" freeport)"
[[ -n "$APP_PORT" ]] || { echo "qa/feature-check.sh: could not find a free port for the app" >&2; exit 2; }
"$PY" -m uvicorn src.main:app --host 127.0.0.1 --port "$APP_PORT" >"${RUNDIR}/app.log" 2>&1 &
APP_PID=$!
BASE="http://127.0.0.1:${APP_PORT}"
if ! "$PY" "$HELPER" wait-health "${BASE}/health" 60; then
  echo "qa/feature-check.sh: the candidate's app never answered ${BASE}/health, so no scenario could be checked:" >&2
  tail -25 "${RUNDIR}/app.log" >&2
  exit 1
fi
echo "The app of this candidate is running at ${BASE} against a throwaway Postgres."
echo

# ----------------------------------------------------------- run the twins
PASSED_TITLES="${RUNDIR}/passed.txt"
: >"$PASSED_TITLES"
RESULTS=()
FAILED=0
for i in "${!TITLES[@]}"; do
  title="${TITLES[$i]}"
  twin="${TWINS[$i]}"
  log="${RUNDIR}/twin-${i}.log"
  marker="fc-${SHORT_SHA}-$$-${i}"
  "$HURL_BIN" \
    --variable "base_url=${BASE}" \
    --variable "host=${BASE}" \
    --variable "run_marker=${marker}" \
    --variable "marker=${marker}" \
    --error-format long \
    "$twin" >"$log" 2>&1
  code=$?
  if [[ $code -eq 0 ]]; then
    RESULTS+=("passed")
    printf '%s\n' "$title" >>"$PASSED_TITLES"
  else
    RESULTS+=("FAILED (hurl exit ${code})")
    FAILED=$((FAILED + 1))
  fi
done

# ---------------------------------------------------------------- the report
printf '%-52.52s %-58.58s %s\n' "Scenario" "Twin" "Result"
printf '%-52.52s %-58.58s %s\n' "----------------------------------------------------" "----------------------------------------------------------" "------"
for i in "${!TITLES[@]}"; do
  printf '%-52.52s %-58.58s %s\n' "${TITLES[$i]}" "${TWINS[$i]}" "${RESULTS[$i]}"
done
if (( ${#OTHER_TITLES[@]} > 0 )); then
  echo
  echo "Not checked here (another verifier owns them):"
  for i in "${!OTHER_TITLES[@]}"; do echo "  - ${OTHER_TITLES[$i]}  [verifier: ${OTHER_VERIFIERS[$i]}]"; done
fi

if (( FAILED > 0 )); then
  echo
  echo "FAILURES — the app did not do what these scenarios promise:"
  for i in "${!TITLES[@]}"; do
    [[ "${RESULTS[$i]}" == "passed" ]] && continue
    echo
    echo "  Scenario: ${TITLES[$i]}"
    echo "  Twin:     ${TWINS[$i]}"
    detail="$(awk '/^error:/{p=1} p' "${RUNDIR}/twin-${i}.log" | head -14)"
    [[ -z "$detail" ]] && detail="$(tail -10 "${RUNDIR}/twin-${i}.log")"
    [[ -z "$detail" ]] && detail="(hurl printed nothing; ${RESULTS[$i]})"
    printf '%s\n' "$detail" | sed 's/^/  | /'
  done
  echo
  echo "Each block above names the twin file and the line of it that failed, with"
  echo "what the app actually returned. Fix the feature so the app answers what the"
  echo "twin asserts — the twins are frozen evidence and must not be edited."
fi

echo
if (( FAILED > 0 )); then
  echo "VERDICT: FAILED — ${FAILED} of ${#TITLES[@]} scenario(s) proven over the wire did not pass."
else
  echo "VERDICT: PASSED — all ${#TITLES[@]} scenario(s) proven over the wire passed against the real app and database."
fi
"$PY" "$HELPER" json-line "$PASSED_TITLES"
(( FAILED > 0 )) && exit 1
exit 0
