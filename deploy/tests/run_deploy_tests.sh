#!/usr/bin/env bash
#
# Dry-run harness proving deploy/deploy.sh logic with a PATH-shimmed fake
# docker + curl (deploy/tests/fake-bin). Asserts, WITHOUT touching the live
# apitest-f2 stack:
#   T1 normal : snapshots the current image as the rollback tag, then `up --build`
#   T2 revert : re-tags $ROLLBACK_IMAGE_REF as the app image, then `up --no-build`
#   T3 revert-missing : loud non-zero fail when the rollback image is absent
#   T4 health-timeout : loud non-zero fail, bounded, when health never comes up
#
# Run: deploy/tests/run_deploy_tests.sh   (exit 0 = all pass)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_SH="$(cd "${HERE}/.." && pwd)/deploy.sh"
FAKE_BIN="${HERE}/fake-bin"

PASS=0
FAIL=0

# Each test runs deploy.sh in an isolated scratch dir with fresh state/logs.
# Echoes captured output + docker/curl invocation logs, then asserts on them.
run_case() {
  local name="$1"
  shift
  local scratch
  scratch="$(mktemp -d)"
  export FAKE_DOCKER_LOG="${scratch}/docker.log"
  export FAKE_DOCKER_STATE="${scratch}/images"
  export FAKE_CURL_LOG="${scratch}/curl.log"
  : >"${FAKE_DOCKER_LOG}"
  : >"${FAKE_DOCKER_STATE}"
  : >"${FAKE_CURL_LOG}"
  # Seed known images (space-separated) via SEED_IMAGES.
  if [[ -n "${SEED_IMAGES:-}" ]]; then
    # SEED_IMAGES is an intentionally space-separated ref list; split to lines.
    # shellcheck disable=SC2086
    printf '%s\n' ${SEED_IMAGES} >>"${FAKE_DOCKER_STATE}"
  fi

  local out rc
  set +e
  out="$(PATH="${FAKE_BIN}:${PATH}" "${DEPLOY_SH}" 2>&1)"
  rc=$?
  set -e

  echo "----- ${name} (exit ${rc}) -----"
  echo "${out}"
  echo "--- docker.log ---"
  cat "${FAKE_DOCKER_LOG}"
  echo "--- curl.log ---"
  cat "${FAKE_CURL_LOG}"
  echo

  # Export for the caller's assertions.
  LAST_OUT="${out}"
  LAST_RC="${rc}"
  LAST_DOCKER_LOG="$(cat "${FAKE_DOCKER_LOG}")"
  LAST_CURL_LOG="$(cat "${FAKE_CURL_LOG}")"
  rm -rf "${scratch}"
}

assert() {
  local desc="$1"
  shift
  if "$@"; then
    echo "  PASS: ${desc}"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: ${desc}"
    FAIL=$((FAIL + 1))
  fi
}

has() { printf '%s' "$2" | grep -qF -- "$1"; }
lacks() { ! printf '%s' "$2" | grep -qF -- "$1"; }
# before "A" "B" "$log": true iff the first line matching A precedes the first
# line matching B (both must be present). Proves ordering, e.g. snapshot-then-retag.
before() {
  local a b hay al bl
  a="$1"; b="$2"; hay="$3"
  al="$(printf '%s\n' "${hay}" | grep -nF -- "${a}" | head -n1 | cut -d: -f1)"
  bl="$(printf '%s\n' "${hay}" | grep -nF -- "${b}" | head -n1 | cut -d: -f1)"
  [[ -n "${al}" && -n "${bl}" && "${al}" -lt "${bl}" ]]
}

# --- T1: NORMAL deploy -------------------------------------------------------
SEED_IMAGES="apitest-f2-app:latest" \
  run_case "T1 normal deploy"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "snapshots current image as rollback tag" \
  has "docker tag apitest-f2-app:latest apitest-app:rollback-pre-deploy" "${LAST_DOCKER_LOG}"
assert "brings the stack up WITH --build" \
  has "docker compose -p apitest-f2 -f docker-compose.yml up -d --build" "${LAST_DOCKER_LOG}"
assert "does NOT use --no-build in normal mode" \
  lacks "--no-build" "${LAST_DOCKER_LOG}"
assert "waited on health (curl called)" \
  has "curl" "${LAST_CURL_LOG}"

# --- T2: REVERT deploy -------------------------------------------------------
REVERT=1 ROLLBACK_IMAGE_REF="apitest-app:rollback-pre-deploy" \
  SEED_IMAGES="apitest-f2-app:latest apitest-app:rollback-pre-deploy" \
  run_case "T2 revert deploy"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "re-tags rollback image as the app image" \
  has "docker tag apitest-app:rollback-pre-deploy apitest-f2-app:latest" "${LAST_DOCKER_LOG}"
assert "brings the stack up WITH --no-build" \
  has "docker compose -p apitest-f2 -f docker-compose.yml up -d --no-build" "${LAST_DOCKER_LOG}"
assert "does NOT rebuild in revert mode" \
  lacks "up -d --build" "${LAST_DOCKER_LOG}"
assert "waited on health (curl called)" \
  has "curl" "${LAST_CURL_LOG}"

# --- T3: REVERT with the rollback image ABSENT -> loud fail ------------------
REVERT=1 ROLLBACK_IMAGE_REF="apitest-app:rollback-pre-deploy" \
  SEED_IMAGES="apitest-f2-app:latest" \
  run_case "T3 revert missing rollback image"
assert "non-zero exit" test "${LAST_RC}" -ne 0
assert "loud FATAL naming the missing rollback image" \
  has "FATAL: rollback image apitest-app:rollback-pre-deploy not found" "${LAST_OUT}"
assert "never ran compose up" \
  lacks "docker compose" "${LAST_DOCKER_LOG}"

# --- T4: health never comes up -> bounded loud fail --------------------------
_t4_start=${SECONDS}
FAKE_CURL_HEALTHY=0 HEALTH_TIMEOUT_SECONDS=2 HEALTH_INTERVAL_SECONDS=1 \
  SEED_IMAGES="apitest-f2-app:latest" \
  run_case "T4 health timeout"
_t4_elapsed=$((SECONDS - _t4_start))
assert "non-zero exit" test "${LAST_RC}" -ne 0
assert "loud FATAL on health timeout" \
  has "did not become healthy within 2s" "${LAST_OUT}"
assert "bounded (<= 10s wall for a 2s timeout)" test "${_t4_elapsed}" -le 10

# --- T5: CANDIDATE deploy ----------------------------------------------------
CANDIDATE=1 SEED_IMAGES="apitest-f2-app:latest" \
  run_case "T5 candidate deploy"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "candidate up on the -cand project with BOTH -f files and --build" \
  has "docker compose -p apitest-f2-cand -f docker-compose.yml -f deploy/docker-compose.candidate.yml up -d --build" "${LAST_DOCKER_LOG}"
assert "probes the CANDIDATE port :8902 (not live :8901)" \
  has "localhost:8902/health" "${LAST_CURL_LOG}"
assert "does NOT probe the live :8901 port" \
  lacks "localhost:8901/health" "${LAST_CURL_LOG}"
assert "takes NO rollback snapshot (candidate is throwaway)" \
  lacks "docker tag apitest-f2-app:latest apitest-app:rollback-pre-deploy" "${LAST_DOCKER_LOG}"
assert "never touches the LIVE project" \
  lacks "-p apitest-f2 " "${LAST_DOCKER_LOG}"

# --- T6: PROMOTE -------------------------------------------------------------
PROMOTE=1 \
  SEED_IMAGES="apitest-f2-app:latest apitest-f2-cand-app:latest" \
  run_case "T6 promote"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "snapshots the current LIVE image as the rollback tag" \
  has "docker tag apitest-f2-app:latest apitest-app:rollback-pre-deploy" "${LAST_DOCKER_LOG}"
assert "re-tags the candidate-built image as the live image" \
  has "docker tag apitest-f2-cand-app:latest apitest-f2-app:latest" "${LAST_DOCKER_LOG}"
assert "snapshot is taken BEFORE the candidate->live re-tag" \
  before "docker tag apitest-f2-app:latest apitest-app:rollback-pre-deploy" \
         "docker tag apitest-f2-cand-app:latest apitest-f2-app:latest" "${LAST_DOCKER_LOG}"
assert "brings the LIVE project up WITH --no-build (no rebuild)" \
  has "docker compose -p apitest-f2 -f docker-compose.yml up -d --no-build" "${LAST_DOCKER_LOG}"
assert "does NOT rebuild in promote mode" \
  lacks "up -d --build" "${LAST_DOCKER_LOG}"
assert "does NOT bring the -cand project up during promote" \
  lacks "-p apitest-f2-cand -f docker-compose.yml -f deploy/docker-compose.candidate.yml up" "${LAST_DOCKER_LOG}"
assert "probes the live :8901 port" \
  has "localhost:8901/health" "${LAST_CURL_LOG}"

# --- T7: PROMOTE with the candidate image ABSENT -> loud fail ----------------
PROMOTE=1 SEED_IMAGES="apitest-f2-app:latest" \
  run_case "T7 promote missing candidate image"
assert "non-zero exit" test "${LAST_RC}" -ne 0
assert "loud FATAL naming the missing candidate image" \
  has "FATAL: candidate image apitest-f2-cand-app:latest not found" "${LAST_OUT}"
assert "never ran compose up" \
  lacks "docker compose" "${LAST_DOCKER_LOG}"
assert "never re-tagged anything (LIVE untouched)" \
  lacks "docker tag" "${LAST_DOCKER_LOG}"

# --- T8: CANDIDATE_DOWN teardown ---------------------------------------------
CANDIDATE_DOWN=1 SEED_IMAGES="apitest-f2-cand-app:latest" \
  run_case "T8 candidate teardown"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "tears the -cand project down WITH volumes + orphans" \
  has "docker compose -p apitest-f2-cand -f docker-compose.yml -f deploy/docker-compose.candidate.yml down -v --remove-orphans" "${LAST_DOCKER_LOG}"
assert "never brings anything up during teardown" \
  lacks "up -d" "${LAST_DOCKER_LOG}"
assert "never touches the LIVE project" \
  lacks "-p apitest-f2 " "${LAST_DOCKER_LOG}"

# --- T9: ambiguous mode combos -> loud refuse, nothing runs ------------------
REVERT=1 CANDIDATE=1 SEED_IMAGES="apitest-f2-app:latest" \
  run_case "T9a ambiguous REVERT+CANDIDATE"
assert "non-zero exit" test "${LAST_RC}" -ne 0
assert "loud FATAL on ambiguous mode signal" \
  has "FATAL: ambiguous mode signal" "${LAST_OUT}"
assert "ran no docker at all" \
  lacks "docker" "${LAST_DOCKER_LOG}"

PROMOTE=1 CANDIDATE=1 SEED_IMAGES="apitest-f2-app:latest apitest-f2-cand-app:latest" \
  run_case "T9b ambiguous PROMOTE+CANDIDATE"
assert "non-zero exit" test "${LAST_RC}" -ne 0
assert "loud FATAL on ambiguous mode signal" \
  has "FATAL: ambiguous mode signal" "${LAST_OUT}"
assert "ran no docker at all" \
  lacks "docker" "${LAST_DOCKER_LOG}"

# --- T10: the candidate overlay is a REPLACE, not an append (static) ---------
_OVERLAY="$(cd "${HERE}/../.." && pwd)/deploy/docker-compose.candidate.yml"
assert "candidate overlay file exists" test -f "${_OVERLAY}"
assert "overlay uses ports: !override (replace, not concatenate)" \
  has "ports: !override" "$(cat "${_OVERLAY}")"
# The overlay must contain this literal (an unexpanded compose var); not shell.
# shellcheck disable=SC2016
assert "overlay maps the CANDIDATE_PORT with the 8902 default" \
  has '${CANDIDATE_PORT:-8902}:8901' "$(cat "${_OVERLAY}")"

# --- summary -----------------------------------------------------------------
echo "================================"
echo "PASS=${PASS} FAIL=${FAIL}"
if [[ "${FAIL}" -ne 0 ]]; then
  exit 1
fi
echo "ALL DEPLOY-SCRIPT TESTS PASSED"
