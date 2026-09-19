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
#      and names it, and nothing is started; a record with scenarios but no
#      hurl stamp at all promised nothing over the wire, so it passes having
#      named nothing as covered;
#   4. otherwise start the candidate's own app against a throwaway Postgres and
#      run each twin with hurl, judging each scenario on its own result;
#   5. print a table, the failures a coder can act on, and one line of JSON
#      naming the scenarios whose twins passed.
#
# Exit 0 is the only pass. Absence never passes: no record, no scenarios, no
# twin, no app, no hurl — all of them fail loudly. Nor does a twin that sends
# no request: each twin is judged on what hurl's own report says it ran.
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
# 2026-09-19: look in both places a bootstrap may have put it, in this order.
PY=""
for candidate in "${ROOT}/.venv/bin/python" "${ROOT}/.guardkit/venv/bin/python"; do
  if [[ -x "$candidate" ]]; then PY="$candidate"; break; fi
done
[[ -n "$PY" ]] || { echo "qa/feature-check.sh: no interpreter at ${ROOT}/.venv/bin/python or ${ROOT}/.guardkit/venv/bin/python — the work leg's bootstrap makes it" >&2; exit 2; }
PY_BIN_DIR="$(dirname "$PY")"
if ! "$PY" -c "import yaml, uvicorn, alembic" >/dev/null 2>&1; then
  "$PY" -m pip install -q -e ".[dev]" >/dev/null 2>&1 || { echo "qa/feature-check.sh: could not install the app and its test extras (.[dev])" >&2; exit 2; }
fi
"$PY" -c "import yaml, uvicorn, alembic" >/dev/null 2>&1 || { echo "qa/feature-check.sh: the worktree venv still has no uvicorn/alembic/pyyaml after installing .[dev]" >&2; exit 2; }

HURL_BIN="${HURL_BIN:-$HOME/.local/bin/hurl}"
if [[ ! -x "$HURL_BIN" ]]; then HURL_BIN="$(command -v hurl 2>/dev/null || true)"; fi
[[ -n "$HURL_BIN" && -x "$HURL_BIN" ]] || { echo "qa/feature-check.sh: no hurl runner found (looked at \$HURL_BIN, \$HOME/.local/bin/hurl and the PATH) — the frozen twins cannot be run" >&2; exit 2; }

# 2026-09-19: a per-REQUEST time limit for hurl, well inside the declared
# feature_check_timeout (900s in .guardkit/config.yaml). An endpoint that never
# answers must fail its own scenario with a message a coder can act on, instead
# of hanging until the factory kills the whole check and nothing is learned.
HURL_MAX_TIME="${HURL_MAX_TIME:-60}"

HELPER="${ROOT}/qa/feature_check_twins.py"
[[ -f "$HELPER" ]] || { echo "qa/feature-check.sh: its own helper ${HELPER} is missing" >&2; exit 2; }

# 2026-09-19: the factory's own timeout kills this shell with a signal no trap
# can catch, so a run that ran out of time can leave its Postgres container
# behind. Before starting anything, sweep exactly that debris and nothing else:
# a container whose name begins with this script's own prefix AND whose trailing
# process id is no longer alive. Any other container — and every volume — is
# left untouched, because this check shares a Docker daemon with real work.
CONTAINER_PREFIX="api-test-feature-check-"
sweep_own_debris() {
  local name pid
  while read -r name; do
    [[ -z "$name" ]] && continue
    [[ "$name" == "${CONTAINER_PREFIX}"* ]] || continue
    pid="${name##*-}"
    [[ "$pid" =~ ^[0-9]+$ ]] || continue          # not one of ours; leave it
    [[ "$pid" == "$$" ]] && continue              # this very run
    [[ -e "/proc/${pid}" ]] && continue           # that run is still going
    kill -0 "$pid" 2>/dev/null && continue        # ditto, owned by someone else
    if docker rm -f "$name" >/dev/null 2>&1; then
      echo "Swept a leftover container from an earlier run of this check: ${name} (its process ${pid} is gone)."
    fi
  done < <(docker ps -a --format '{{.Names}}' 2>/dev/null || true)
}
sweep_own_debris

RUNDIR="$(mktemp -d -t api-test-feature-check-XXXXXX)"
PG_NAME="${CONTAINER_PREFIX}${SHORT_SHA}-$$"
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
  # 2026-09-19: a record with scenarios, none of them stamped `verifier: hurl`,
  # is not missing evidence — nothing in this feature was promised over the
  # wire, so this check has nothing to do and says so. It names NOTHING as
  # covered, which is what matters: the factory's completion rule still blocks
  # the merge if a pass bar promised something no verifier proved.
  echo "nothing in this feature is proven over the wire by this check"
  echo
  echo "The feature record names scenarios, but not one of them is stamped"
  echo "'verifier: hurl', so none of them was promised at the wire surface this"
  echo "check exercises. Nothing was started and nothing is claimed as covered."
  if (( ${#OTHER_TITLES[@]} > 0 )); then
    echo
    echo "Not checked here (another verifier owns them):"
    for i in "${!OTHER_TITLES[@]}"; do echo "  - ${OTHER_TITLES[$i]}  [verifier: ${OTHER_VERIFIERS[$i]}]"; done
  fi
  echo
  : >"${RUNDIR}/passed.txt"
  "$PY" "$HELPER" json-line "${RUNDIR}/passed.txt"
  exit 0
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
export PATH="${PY_BIN_DIR}:${PATH}"

# The candidate's own migrations, exactly as the container entrypoint runs them.
ALEMBIC="${PY_BIN_DIR}/alembic"
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
REASONS=()
FAILED=0
for i in "${!TITLES[@]}"; do
  title="${TITLES[$i]}"
  twin="${TWINS[$i]}"
  log="${RUNDIR}/twin-${i}.log"
  report="${RUNDIR}/report-${i}"
  marker="fc-${SHORT_SHA}-$$-${i}"
  "$HURL_BIN" \
    --variable "base_url=${BASE}" \
    --variable "host=${BASE}" \
    --variable "run_marker=${marker}" \
    --variable "marker=${marker}" \
    --error-format long \
    --max-time "$HURL_MAX_TIME" \
    --report-json "$report" \
    "$twin" >"$log" 2>&1
  code=$?
  # What hurl ACTUALLY ran, from its own machine-readable report, not from its
  # exit code: a file of comments exits 0 having sent nothing at all.
  sent="$("$PY" "$HELPER" report-requests "${report}/report.json" 2>/dev/null || echo -1)"
  [[ "$sent" =~ ^-?[0-9]+$ ]] || sent=-1
  if (( sent == 0 )); then
    RESULTS+=("FAILED (no request sent)")
    REASONS+=("this twin sends no request, so it proves nothing")
    FAILED=$((FAILED + 1))
  elif (( sent < 0 )); then
    RESULTS+=("FAILED (no report)")
    REASONS+=("hurl wrote no readable report for this twin, so this check cannot tell what it ran")
    FAILED=$((FAILED + 1))
  elif [[ $code -eq 0 ]]; then
    RESULTS+=("passed")
    REASONS+=("")
    printf '%s\n' "$title" >>"$PASSED_TITLES"
  else
    RESULTS+=("FAILED (hurl exit ${code})")
    REASONS+=("")
    FAILED=$((FAILED + 1))
  fi
done

# ---------------------------------------------------------------- the report
# 2026-09-19: no fixed byte widths. Titles are people's sentences and carry
# accents; a byte-counted column cut them in the middle of a character and
# printed mojibake. Rows go out tab-separated and the helper lines them up by
# CHARACTER count. Not `column -t`: outside a UTF-8 locale that tool rewrites
# every accented character as a \xNN escape — driven and seen, 2026-09-19.
TABLE="${RUNDIR}/table.tsv"
{
  printf 'Scenario\tTwin\tResult\n'
  for i in "${!TITLES[@]}"; do
    printf '%s\t%s\t%s\n' "${TITLES[$i]}" "${TWINS[$i]}" "${RESULTS[$i]}"
  done
} >"$TABLE"
"$PY" "$HELPER" table "$TABLE" || cat "$TABLE"
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
    if [[ -n "${REASONS[$i]}" ]]; then
      printf '  | %s\n' "${REASONS[$i]}"
      continue
    fi
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
