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
#   3. a stamped scenario with no twin is NOT CHECKED — it is named here and in
#      the line of JSON, and it is never claimed as covered; the same for a
#      scenario another verifier owns;
#   4. start the candidate's own app against a throwaway Postgres and run each
#      twin that DOES exist with hurl, judging each scenario on its own result;
#   5. ask the feature's own entry point two plain questions of the running
#      product and write down what it answered (see `observe` in the helper);
#   6. print a table, the failures a coder can act on, and one line of JSON
#      naming what passed, what nothing looked at, and what was asked.
#
# 2026-09-21 (way-forward plan, parts 1 and 2). This check used to STOP DEAD
# when a stamped scenario had no twin — nothing was started, so a build could
# be discarded with no evidence at all about the finished feature, and a merge
# card could say nothing about what it does. It no longer refuses. An example
# nothing looked at is reported as NOT CHECKED and is never recorded as passed.
# The owner's answer of 21 September 2026: "Q1: yes mark it not checked".
#
# Three outcomes, kept apart, because they are different things:
#   * PASSED (exit 0)        every twin that exists ran and passed;
#   * FAILED (exit 1)        something ran and did not pass, or the product
#                            would not start, or its migrations failed — this
#                            is what the factory's bounded repair is for;
#   * COULD NOT RUN (exit 2) the environment this check needs is not here (no
#                            container runtime, no interpreter, no hurl for the
#                            twins that exist). Said in so many words in the
#                            line of JSON. Neither a pass nor a fault of the
#                            build, so nothing is sent back for repair.
# "Not checked" is never recorded as passed, anywhere.
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
# 2026-09-21: an environment fault says so ON STDOUT, in the one line of JSON,
# before this check gives up. The factory reads that line and records "could
# not run" — its own third outcome, neither a pass nor something to repair.
# Written without the helper too, because two of these faults are that there is
# no interpreter to run it with.
PY=""
HELPER=""
emit_could_not_run() {
  local reason="$1" safe
  if [[ -n "$PY" && -x "$PY" && -n "$HELPER" && -f "$HELPER" ]]; then
    "$PY" "$HELPER" could-not-run "$reason" && return 0
  fi
  safe="$(printf '%s' "$reason" | tr -d '"\\' | tr '\n\r\t' '   ')"
  printf '{"guardkit_feature_check": {"could_not_run": "%s"}}\n' "$safe"
}
could_not_run() {   # could_not_run <reason>  — say it, then stop
  echo "COULD NOT RUN — ${1}" >&2
  emit_could_not_run "$1"
  exit 2
}

for candidate in "${ROOT}/.venv/bin/python" "${ROOT}/.guardkit/venv/bin/python"; do
  if [[ -x "$candidate" ]]; then PY="$candidate"; break; fi
done
[[ -n "$PY" ]] || could_not_run "qa/feature-check.sh: no interpreter at ${ROOT}/.venv/bin/python or ${ROOT}/.guardkit/venv/bin/python — the work leg's bootstrap makes it"
PY_BIN_DIR="$(dirname "$PY")"
if ! "$PY" -c "import yaml, uvicorn, alembic" >/dev/null 2>&1; then
  "$PY" -m pip install -q -e ".[dev]" >/dev/null 2>&1 || could_not_run "qa/feature-check.sh: could not install the app and its test extras (.[dev])"
fi
"$PY" -c "import yaml, uvicorn, alembic" >/dev/null 2>&1 || could_not_run "qa/feature-check.sh: the worktree venv still has no uvicorn/alembic/pyyaml after installing .[dev]"

# hurl is resolved here but only REQUIRED once the scenarios are read: a
# feature with no twin file to run needs no runner for them, and refusing then
# would hide what the product does behind a missing tool.
HURL_BIN="${HURL_BIN:-$HOME/.local/bin/hurl}"
if [[ ! -x "$HURL_BIN" ]]; then HURL_BIN="$(command -v hurl 2>/dev/null || true)"; fi

# 2026-09-19: a per-REQUEST time limit for hurl, well inside the declared
# feature_check_timeout (900s in .guardkit/config.yaml). An endpoint that never
# answers must fail its own scenario with a message a coder can act on, instead
# of hanging until the factory kills the whole check and nothing is learned.
HURL_MAX_TIME="${HURL_MAX_TIME:-60}"

HELPER="${ROOT}/qa/feature_check_twins.py"
[[ -f "$HELPER" ]] || { HELPER=""; could_not_run "qa/feature-check.sh: its own helper ${ROOT}/qa/feature_check_twins.py is missing"; }

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
    # -v: without it every forced removal left an unattached volume behind,
    # and 542 of them had piled up by 2026-09-19.
    if docker rm -f -v "$name" >/dev/null 2>&1; then
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
  docker rm -f -v "$PG_NAME" >/dev/null 2>&1
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

# --------------------------------------------------------- what NOTHING checks
# 2026-09-21: this used to be two refusals. A stamped scenario with no twin
# printed MISSING EVIDENCE and exited 1 without starting anything, and a record
# with no stamped scenario at all printed "nothing was started" and exited 0.
# Both are now the same, plainer thing: the examples nothing looked at are
# NAMED, here and in the line of JSON, and the product is started anyway.
NOT_CHECKED="${RUNDIR}/not-checked.tsv"
: >"$NOT_CHECKED"
if (( ${#MISSING[@]} > 0 )); then
  echo "NOT CHECKED — ${#MISSING[@]} scenario(s) stamped 'verifier: hurl' have no frozen twin file:"
  for title in "${MISSING[@]}"; do
    echo "  - ${title}"
    printf '%s\t%s\n' "$title" "no frozen twin file exists for this example, so nothing checked it" >>"$NOT_CHECKED"
  done
  echo
  echo "To check them, write one twin file per scenario under qa/twins/<feature-area>/,"
  echo "named for the scenario (for example qa/twins/time-endpoint/reading-current-server-time.hurl)."
  echo "Either point the scenario's stamp at it with"
  echo "    test_ref: qa/twins/<feature-area>/<file>.hurl"
  echo "or give the twin a comment line carrying the scenario title exactly:"
  echo "    # Scenario: <the scenario title, character for character>"
  echo "The twin addresses the app as {{base_url}} and may use {{run_marker}} for"
  echo "unique test data. None of these is recorded as passed."
  echo
fi
if (( ${#OTHER_TITLES[@]} > 0 )); then
  echo "NOT CHECKED HERE — another verifier owns these scenarios:"
  for i in "${!OTHER_TITLES[@]}"; do
    echo "  - ${OTHER_TITLES[$i]}  [verifier: ${OTHER_VERIFIERS[$i]}]"
    printf '%s\t%s\n' "${OTHER_TITLES[$i]}" "another verifier owns this example: ${OTHER_VERIFIERS[$i]}" >>"$NOT_CHECKED"
  done
  echo
fi
if (( ${#TITLES[@]} == 0 )); then
  echo "No scenario of this feature has a frozen twin to run, so this check runs none."
  echo "It still starts the product and asks the feature's own entry point what it answers."
  echo
elif [[ -z "$HURL_BIN" || ! -x "$HURL_BIN" ]]; then
  could_not_run "qa/feature-check.sh: ${#TITLES[@]} scenario(s) have a frozen twin to run and no hurl runner was found (looked at \$HURL_BIN, \$HOME/.local/bin/hurl and the PATH)"
fi

# ------------------------------------------------------- the real database
command -v docker >/dev/null 2>&1 || could_not_run "qa/feature-check.sh: there is no container runtime here, so the throwaway database this check needs cannot be started"
docker info >/dev/null 2>&1 || could_not_run "qa/feature-check.sh: the container runtime is not answering, so the throwaway database this check needs cannot be started"
docker run -d --rm --name "$PG_NAME" \
  -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test \
  --tmpfs /var/lib/postgresql/data \
  -p "127.0.0.1:0:5432" postgres:16-alpine >/dev/null 2>"${RUNDIR}/pg.err"
if [[ $? -ne 0 ]]; then
  could_not_run "qa/feature-check.sh: the throwaway Postgres could not be started: $(tail -3 "${RUNDIR}/pg.err" | tr '\n' ' ')"
fi
PG_PORT="$(docker port "$PG_NAME" 5432/tcp | head -1 | sed -E 's/.*:([0-9]+)$/\1/')"
[[ -n "$PG_PORT" ]] || could_not_run "qa/feature-check.sh: the throwaway Postgres started but its port could not be read"
PG_READY=""
for _ in $(seq 1 60); do
  docker exec "$PG_NAME" pg_isready -U postgres >/dev/null 2>&1 && { PG_READY=yes; break; }
  sleep 1
done
[[ -n "$PG_READY" ]] || could_not_run "qa/feature-check.sh: the throwaway Postgres never became ready"

export DATABASE_URL="postgresql+asyncpg://postgres:test@127.0.0.1:${PG_PORT}/test"
export PATH="${PY_BIN_DIR}:${PATH}"

# The candidate's own migrations, exactly as the container entrypoint runs them.
ALEMBIC="${PY_BIN_DIR}/alembic"
if [[ -x "$ALEMBIC" ]]; then "$ALEMBIC" upgrade head >"${RUNDIR}/alembic.log" 2>&1
else "$PY" -m alembic upgrade head >"${RUNDIR}/alembic.log" 2>&1; fi
if [[ $? -ne 0 ]]; then
  echo "qa/feature-check.sh: the candidate's migrations (alembic upgrade head) failed, so the app could not be started:" >&2
  tail -20 "${RUNDIR}/alembic.log" >&2
  # A product that will not start is a FAILURE, not "could not run": it is
  # exactly what the factory's bounded repair is for.
  : >"${RUNDIR}/passed.txt"
  "$PY" "$HELPER" json-line "${RUNDIR}/passed.txt" "$NOT_CHECKED"
  exit 1
fi

# ------------------------------------------------------------- the real app
APP_PORT="$("$PY" "$HELPER" freeport)"
[[ -n "$APP_PORT" ]] || could_not_run "qa/feature-check.sh: no free port could be found for the app"
"$PY" -m uvicorn src.main:app --host 127.0.0.1 --port "$APP_PORT" >"${RUNDIR}/app.log" 2>&1 &
APP_PID=$!
BASE="http://127.0.0.1:${APP_PORT}"
if ! "$PY" "$HELPER" wait-health "${BASE}/health" 60; then
  echo "qa/feature-check.sh: the candidate's app never answered ${BASE}/health, so no scenario could be checked:" >&2
  tail -25 "${RUNDIR}/app.log" >&2
  : >"${RUNDIR}/passed.txt"
  "$PY" "$HELPER" json-line "${RUNDIR}/passed.txt" "$NOT_CHECKED"
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
for i in $(seq 0 $(( ${#TITLES[@]} - 1 ))); do
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

# --------------------------------------------------------- the observations
# 2026-09-21. Besides running whatever twins exist, ask the feature's OWN entry
# point what it answers, while the real product is up on a real database: once
# with nothing stored, then after a few records made through the product's own
# published create call, then once more. Each question and its answer goes in
# the line of JSON so a person reading the merge card can see what the finished
# feature does. This check compares nothing and decides nothing about them; a
# scenario is never marked passed or failed on an observation.
#
# UNRESOLVED, and said here as well as in the design: how to choose useful
# questions for an arbitrary feature. These are the two plainest states, and
# they will not always expose a fault — which is why the card carries what was
# ASKED as well as what came back, so silence is never read as proof.
ENTRY_JSON="${RUNDIR}/entry-point.json"
OBSERVATIONS="${RUNDIR}/observations.json"
if ! "$PY" "$HELPER" entry-point "$ROOT" >"$ENTRY_JSON" 2>"${RUNDIR}/entry.err"; then
  printf '{"found": false, "reason": "the feature entry point could not be looked up: %s"}\n' \
    "$(tr -d '"\\' <"${RUNDIR}/entry.err" | tr '\n' ' ' | cut -c1-200)" >"$ENTRY_JSON"
fi
if ! "$PY" "$HELPER" observe "$BASE" "$ENTRY_JSON" >"$OBSERVATIONS" 2>"${RUNDIR}/observe.err"; then
  echo '{"observations": []}' >"$OBSERVATIONS"
  printf '%s\t%s\n' "what the finished feature answers" \
    "the product could not be asked: $(tr -d '"\\' <"${RUNDIR}/observe.err" | tr '\n' ' ' | cut -c1-200)" >>"$NOT_CHECKED"
fi
# Anything `observe` said it could not do joins the not-checked list.
"$PY" - "$OBSERVATIONS" "$NOT_CHECKED" <<'PY' || true
import json, sys
try:
    data = json.loads(open(sys.argv[1], encoding="utf-8").read())
except Exception:
    raise SystemExit(0)
rows = data.get("not_checked") if isinstance(data, dict) else None
if isinstance(rows, list) and rows:
    with open(sys.argv[2], "a", encoding="utf-8") as handle:
        for row in rows:
            if isinstance(row, dict) and row.get("name"):
                handle.write(f"{row['name']}\t{row.get('reason', '')}\n")
PY
echo "WHAT THE FINISHED FEATURE ANSWERED (observed, not judged):"
"$PY" - "$OBSERVATIONS" <<'PY' || echo "  (nothing was asked)"
import json, sys
try:
    data = json.loads(open(sys.argv[1], encoding="utf-8").read())
except Exception:
    data = {}
rows = (data or {}).get("observations") or []
if not rows:
    print("  (nothing was asked)")
for row in rows:
    print(f"  asked:    {row.get('asked', '')}")
    print(f"  answered: {row.get('answered', '')}")
PY
echo

# ---------------------------------------------------------------- the report
# 2026-09-19: no fixed byte widths. Titles are people's sentences and carry
# accents; a byte-counted column cut them in the middle of a character and
# printed mojibake. Rows go out tab-separated and the helper lines them up by
# CHARACTER count. Not `column -t`: outside a UTF-8 locale that tool rewrites
# every accented character as a \xNN escape — driven and seen, 2026-09-19.
if (( ${#TITLES[@]} > 0 )); then
  TABLE="${RUNDIR}/table.tsv"
  {
    printf 'Scenario\tTwin\tResult\n'
    for i in $(seq 0 $(( ${#TITLES[@]} - 1 ))); do
      printf '%s\t%s\t%s\n' "${TITLES[$i]}" "${TWINS[$i]}" "${RESULTS[$i]}"
    done
  } >"$TABLE"
  "$PY" "$HELPER" table "$TABLE" || cat "$TABLE"
fi

if (( FAILED > 0 )); then
  echo
  echo "FAILURES — the app did not do what these scenarios promise:"
  for i in $(seq 0 $(( ${#TITLES[@]} - 1 ))); do
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
NOT_CHECKED_COUNT="$(wc -l <"$NOT_CHECKED" | tr -d ' ')"
if (( FAILED > 0 )); then
  echo "VERDICT: FAILED — ${FAILED} of ${#TITLES[@]} scenario(s) with a frozen twin did not pass."
elif (( ${#TITLES[@]} > 0 )); then
  echo "VERDICT: PASSED — all ${#TITLES[@]} scenario(s) with a frozen twin passed against the real app and database."
else
  echo "VERDICT: PASSED — no scenario of this feature had a frozen twin to run, so this check names none as covered."
fi
if (( NOT_CHECKED_COUNT > 0 )); then
  echo "NOT CHECKED: ${NOT_CHECKED_COUNT} item(s), named above and in the line below. None of them is recorded as passed."
fi
"$PY" "$HELPER" json-line "$PASSED_TITLES" "$NOT_CHECKED" "$OBSERVATIONS"
(( FAILED > 0 )) && exit 1
exit 0
