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

# --- summary -----------------------------------------------------------------
echo "================================"
echo "PASS=${PASS} FAIL=${FAIL}"
if [[ "${FAIL}" -ne 0 ]]; then
  exit 1
fi
echo "ALL DEPLOY-SCRIPT TESTS PASSED"
