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
# SCRATCH, when the caller sets it, is a directory this case SHARES with the
# cases around it: the fake docker's image store survives from one run of
# deploy.sh to the next, which is what a two-leg scenario needs — the candidate
# leg builds and names an image, and the promote that follows has to find it by
# the id the candidate reported. Unset (every single-leg case) ⇒ a fresh
# throwaway directory, exactly as before.
run_case() {
  local name="$1"
  shift
  local scratch shared
  shared="${SCRATCH:-}"
  if [[ -n "${shared}" ]]; then
    scratch="${shared}"
    mkdir -p "${scratch}"
  else
    scratch="$(mktemp -d)"
  fi
  export FAKE_DOCKER_LOG="${scratch}/docker.log"
  export FAKE_DOCKER_STATE="${scratch}/images"
  export FAKE_CURL_LOG="${scratch}/curl.log"
  : >"${FAKE_DOCKER_LOG}"
  : >"${FAKE_CURL_LOG}"
  if [[ -z "${shared}" || ! -f "${FAKE_DOCKER_STATE}" ]]; then
    : >"${FAKE_DOCKER_STATE}"
  fi
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
  LAST_STATE="$(cat "${FAKE_DOCKER_STATE}")"
  if [[ -z "${shared}" ]]; then
    rm -rf "${scratch}"
  fi
}

# The one line of a run's output that carries "<marker>=<value>", value only.
said() {
  printf '%s\n' "${2}" | grep -oE "^${1}=.*$" | tail -n1 | cut -d= -f2-
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
# WHOLE-LINE match. An empty value is meaningful in the read-only answer — it
# is how a project says nothing is running — so "RUNNING_IDENTITY=" has to be
# asked about as the whole line, never as a fragment of a longer one.
has_line() { printf '%s\n' "$2" | grep -qxF -- "$1"; }
lacks_line() { ! printf '%s\n' "$2" | grep -qxF -- "$1"; }
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
# Changed 24 September 2026: the candidate leg is where the artifact's identity
# is CAPTURED, so it is handed the identity and reports the built image's id.
# Changed AGAIN 25 September 2026, after the third review. The check used to
# resolve the SHARED compose-built name after the health check; it now runs on
# a compose project of its own and reads the image off the container it started.
_T5_IDENTITY="j-0123456789ab@ffeeddccbbaa9988"
_T5_PROJECT="apitest-f2-cand-j-0123456789ab-ffeeddccbbaa9988"
_T5_IMAGE="sha256:fake-${_T5_PROJECT}-app_latest"
CANDIDATE=1 DEPLOY_IDENTITY="${_T5_IDENTITY}" \
  SEED_IMAGES="apitest-f2-app:latest" \
  run_case "T5 candidate deploy"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "the candidate project is THIS CHECK'S OWN, made from the identity" \
  has "docker compose -p ${_T5_PROJECT} -f docker-compose.yml -f deploy/docker-compose.candidate.yml up -d --build" "${LAST_DOCKER_LOG}"
assert "no other build's check can share it: the old shared -cand name is never used" \
  lacks "-p apitest-f2-cand " "${LAST_DOCKER_LOG}"
assert "asks THE PROJECT IT STARTED which container is up" \
  has "docker compose -p ${_T5_PROJECT} -f docker-compose.yml ps -q app" "${LAST_DOCKER_LOG}"
assert "reads the image off THAT CONTAINER, by container id" \
  has "docker inspect --format {{.Image}} ${_T5_PROJECT}-app-1" "${LAST_DOCKER_LOG}"
assert "never resolves a shared compose-built image name" \
  lacks "docker image inspect --format {{.Id}} apitest-f2-cand" "${LAST_DOCKER_LOG}"
assert "names the container's own image with the identity, at the CHECK" \
  has "docker tag ${_T5_IMAGE} apitest-app:j-0123456789ab-ffeeddccbbaa9988" "${LAST_DOCKER_LOG}"
assert "REPORTS that image's own id, which is what forge records" \
  has "CHECKED_ARTIFACT=${_T5_IMAGE}" "${LAST_OUT}"
assert "probes the CANDIDATE port :8902 (not live :8901)" \
  has "localhost:8902/health" "${LAST_CURL_LOG}"
assert "does NOT probe the live :8901 port" \
  lacks "localhost:8901/health" "${LAST_CURL_LOG}"
assert "takes NO rollback snapshot (candidate is throwaway)" \
  lacks "docker tag apitest-f2-app:latest apitest-app:rollback-pre-deploy" "${LAST_DOCKER_LOG}"
assert "never touches the LIVE project" \
  lacks "-p apitest-f2 " "${LAST_DOCKER_LOG}"

# --- T5b: two checks in flight do not share a project, a container or an image
_T5B_A="j-aaaa11112222@1111"
_T5B_B="j-bbbb33334444@2222"
_T5B_DIR="$(mktemp -d)"
SCRATCH="${_T5B_DIR}" CANDIDATE=1 DEPLOY_IDENTITY="${_T5B_A}" \
  SEED_IMAGES="apitest-f2-app:latest" \
  run_case "T5b A's check"
assert "A's check passed" test "${LAST_RC}" -eq 0
_T5B_A_ARTIFACT="$(said CHECKED_ARTIFACT "${LAST_OUT}")"
SCRATCH="${_T5B_DIR}" CANDIDATE=1 DEPLOY_IDENTITY="${_T5B_B}" \
  run_case "T5b B's check, while A's is up"
assert "B's check passed" test "${LAST_RC}" -eq 0
_T5B_B_ARTIFACT="$(said CHECKED_ARTIFACT "${LAST_OUT}")"
assert "A and B checked DIFFERENT artifacts" \
  test "${_T5B_A_ARTIFACT}" != "${_T5B_B_ARTIFACT}"
assert "A's candidate container is still A's, untouched by B" \
  has "container:apitest-f2-cand-j-aaaa11112222-1111-app-1 ${_T5B_A_ARTIFACT}" "${LAST_STATE}"
rm -rf "${_T5B_DIR}"

# --- T6: PROMOTE, by the artifact captured at the check ----------------------
# Changed AGAIN 24 September 2026, after the stage's second review. The 23
# September promote still RESOLVED THE SHARED CANDIDATE NAME and only then gave
# what it found the identity's tag, so a build that replaced that name between
# the check and the promote had its image put live under somebody else's
# identity. The artifact is captured at the check now (T5) and handed back here
# as $DEPLOY_ARTIFACT — an image id, which nothing can move onto another image.
PROMOTE=1 DEPLOY_IDENTITY="j-0123456789ab@ffeeddccbbaa9988" \
  DEPLOY_ARTIFACT="sha256:fake-apitest-f2-cand-app_latest" \
  SEED_IMAGES="apitest-f2-app:latest apitest-f2-cand-app:latest" \
  run_case "T6 promote"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "names the RECORDED ARTIFACT with the identity it was handed" \
  has "docker tag sha256:fake-apitest-f2-cand-app_latest apitest-app:j-0123456789ab-ffeeddccbbaa9988" "${LAST_DOCKER_LOG}"
assert "snapshots the current LIVE image as the rollback tag" \
  has "docker tag apitest-f2-app:latest apitest-app:rollback-pre-deploy" "${LAST_DOCKER_LOG}"
assert "promotes THE RECORDED ARTIFACT, by its own id" \
  has "docker tag sha256:fake-apitest-f2-cand-app_latest apitest-f2-app:latest" "${LAST_DOCKER_LOG}"
assert "never reads the shared candidate name at all" \
  lacks "apitest-f2-cand-app:latest" "${LAST_DOCKER_LOG}"
assert "snapshot is taken BEFORE the artifact->live re-tag" \
  before "docker tag apitest-f2-app:latest apitest-app:rollback-pre-deploy" \
         "docker tag sha256:fake-apitest-f2-cand-app_latest apitest-f2-app:latest" "${LAST_DOCKER_LOG}"
assert "brings the LIVE project up WITH --no-build (no rebuild)" \
  has "docker compose -p apitest-f2 -f docker-compose.yml up -d --no-build" "${LAST_DOCKER_LOG}"
assert "does NOT rebuild in promote mode" \
  lacks "up -d --build" "${LAST_DOCKER_LOG}"
assert "does NOT bring the -cand project up during promote" \
  lacks "-p apitest-f2-cand -f docker-compose.yml -f deploy/docker-compose.candidate.yml up" "${LAST_DOCKER_LOG}"
assert "probes the live :8901 port" \
  has "localhost:8901/health" "${LAST_CURL_LOG}"
assert "asks compose which container is running" \
  has "docker compose -p apitest-f2 -f docker-compose.yml ps -q app" "${LAST_DOCKER_LOG}"
assert "INSPECTS THE RUNNING CONTAINER, not a tag" \
  has "docker inspect --format {{.Image}} apitest-f2-app-1" "${LAST_DOCKER_LOG}"
assert "REPORTS the identity of what is now running, on one line forge reads" \
  has "DEPLOYED_IDENTITY=j-0123456789ab@ffeeddccbbaa9988" "${LAST_OUT}"
assert "REPORTS the artifact the running container was started from" \
  has "DEPLOYED_ARTIFACT=sha256:fake-apitest-f2-cand-app_latest" "${LAST_OUT}"

# --- T6b: PROMOTE with NO identity -> loud refusal ---------------------------
# The shared name is the defect this change removes, so a promote with nothing
# to promote BY refuses rather than falling back to it.
PROMOTE=1 \
  SEED_IMAGES="apitest-f2-app:latest apitest-f2-cand-app:latest" \
  run_case "T6b promote with no identity"
assert "non-zero exit" test "${LAST_RC}" -ne 0
assert "loud FATAL saying why" \
  has "FATAL: no DEPLOY_IDENTITY was handed to this promote" "${LAST_OUT}"
assert "never re-tagged anything (LIVE untouched)" \
  lacks "docker tag" "${LAST_DOCKER_LOG}"
assert "never ran compose up" \
  lacks "docker compose" "${LAST_DOCKER_LOG}"

# --- T6c: PROMOTE with an identity but NO recorded artifact -> loud refusal --
# Without the artifact this leg would have to resolve the shared candidate name,
# which is the defect. It refuses instead.
PROMOTE=1 DEPLOY_IDENTITY="j-0123456789ab@ffeeddccbbaa9988" \
  SEED_IMAGES="apitest-f2-app:latest apitest-f2-cand-app:latest" \
  run_case "T6c promote with no recorded artifact"
assert "non-zero exit" test "${LAST_RC}" -ne 0
assert "loud FATAL saying why" \
  has "FATAL: no DEPLOY_ARTIFACT was handed to this promote" "${LAST_OUT}"
assert "never re-tagged anything (LIVE untouched)" \
  lacks "docker tag" "${LAST_DOCKER_LOG}"
assert "never ran compose up" \
  lacks "docker compose" "${LAST_DOCKER_LOG}"

# --- T7: PROMOTE with the recorded artifact GONE -> loud fail ----------------
PROMOTE=1 DEPLOY_IDENTITY="j-0123456789ab@ffeeddccbbaa9988" \
  DEPLOY_ARTIFACT="sha256:fake-nothing-has-this-id" \
  SEED_IMAGES="apitest-f2-app:latest apitest-f2-cand-app:latest" \
  run_case "T7 promote with the recorded artifact gone"
assert "non-zero exit" test "${LAST_RC}" -ne 0
assert "loud FATAL naming the artifact that was checked" \
  has "FATAL: the artifact that was checked (sha256:fake-nothing-has-this-id) is not here any more" "${LAST_OUT}"
assert "says the shared name is not a substitute" \
  has "the shared candidate name is not a substitute for it" "${LAST_OUT}"
assert "never ran compose up" \
  lacks "docker compose" "${LAST_DOCKER_LOG}"
assert "never re-tagged anything (LIVE untouched)" \
  lacks "docker tag" "${LAST_DOCKER_LOG}"

# --- T8: CANDIDATE_DOWN teardown ---------------------------------------------
# Changed 25 September 2026 with the candidate project. A teardown handed the
# same identity as the check tears down exactly that check's project.
CANDIDATE_DOWN=1 DEPLOY_IDENTITY="${_T5_IDENTITY}" \
  run_case "T8 candidate teardown, by the identity it was handed"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "tears THAT CHECK'S project down WITH volumes + orphans" \
  has "docker compose -p ${_T5_PROJECT} -f docker-compose.yml -f deploy/docker-compose.candidate.yml down -v --remove-orphans" "${LAST_DOCKER_LOG}"
assert "never brings anything up during teardown" \
  lacks "up -d" "${LAST_DOCKER_LOG}"
assert "never touches the LIVE project" \
  lacks "-p apitest-f2 " "${LAST_DOCKER_LOG}"

# --- T8b: a teardown handed nothing GOES AND LOOKS ---------------------------
# There is no single shared name to assume any more, so a teardown with no
# identity asks docker which candidate projects of this repository are up.
_T8B_DIR="$(mktemp -d)"
SCRATCH="${_T8B_DIR}" CANDIDATE=1 DEPLOY_IDENTITY="${_T5_IDENTITY}" \
  SEED_IMAGES="apitest-f2-app:latest" \
  run_case "T8b a check, so there is something to find"
assert "the check passed" test "${LAST_RC}" -eq 0
SCRATCH="${_T8B_DIR}" CANDIDATE_DOWN=1 \
  run_case "T8b teardown with nothing handed to it"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "asks docker which projects are up" \
  has "docker compose ls --all -q" "${LAST_DOCKER_LOG}"
assert "tears down the candidate project it FOUND" \
  has "docker compose -p ${_T5_PROJECT} -f docker-compose.yml -f deploy/docker-compose.candidate.yml down -v --remove-orphans" "${LAST_DOCKER_LOG}"
assert "never tears the LIVE project down" \
  lacks "-p apitest-f2 -f docker-compose.yml -f deploy/docker-compose.candidate.yml down" "${LAST_DOCKER_LOG}"
rm -rf "${_T8B_DIR}"

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

# --- T11: A NAME IS REPLACED BETWEEN A'S CHECK AND A'S PROMOTE ---------------
# The failure a reviewer drove on 24 September 2026 with a fake docker: A was
# checked, B replaced the candidate image name, and A's promote deployed B
# while reporting A's identity. Both legs run here against ONE image store, so
# the window is real rather than described.
_T11_DIR="$(mktemp -d)"
_A_IDENTITY="j-aaaaaaaaaaaa@1111111111111111"
_A_PROJECT="apitest-f2-cand-j-aaaaaaaaaaaa-1111111111111111"

SCRATCH="${_T11_DIR}" CANDIDATE=1 DEPLOY_IDENTITY="${_A_IDENTITY}" \
  SEED_IMAGES="apitest-f2-app:latest" \
  run_case "T11a A's candidate check"
assert "A's check passed" test "${LAST_RC}" -eq 0
_A_ARTIFACT="$(said CHECKED_ARTIFACT "${LAST_OUT}")"
assert "A's check captured an artifact id" test -n "${_A_ARTIFACT}"

# A second build now replaces the compose-built image NAME with its own image,
# exactly as a build in flight does.
printf 'build-b-app:latest sha256:fake-BUILD-B\n' >>"${_T11_DIR}/images"
FAKE_DOCKER_LOG="${_T11_DIR}/docker.log" FAKE_DOCKER_STATE="${_T11_DIR}/images" \
  PATH="${FAKE_BIN}:${PATH}" docker tag build-b-app:latest "${_A_PROJECT}-app:latest"

SCRATCH="${_T11_DIR}" PROMOTE=1 DEPLOY_IDENTITY="${_A_IDENTITY}" \
  DEPLOY_ARTIFACT="${_A_ARTIFACT}" \
  run_case "T11b A's promote, with the candidate name now B's"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "the candidate image name now points at B" \
  has "${_A_PROJECT}-app:latest sha256:fake-BUILD-B" "${LAST_STATE}"
assert "A PROMOTES A: the live tag is given A's recorded artifact" \
  has "docker tag ${_A_ARTIFACT} apitest-f2-app:latest" "${LAST_DOCKER_LOG}"
assert "B's image is never named anywhere in the promote" \
  lacks "sha256:fake-BUILD-B" "${LAST_DOCKER_LOG}"
assert "the candidate image NAME is never read (only the recorded id is)" \
  lacks "${_A_PROJECT}-app:latest" "${LAST_DOCKER_LOG}"
assert "what is RUNNING is A's artifact, read off the container" \
  has "DEPLOYED_ARTIFACT=${_A_ARTIFACT}" "${LAST_OUT}"
assert "and it reports A's identity, because A is what is running" \
  has "DEPLOYED_IDENTITY=${_A_IDENTITY}" "${LAST_OUT}"

# --- T12: RUNNING_IDENTITY — read-only, and it changes nothing ---------------
SCRATCH="${_T11_DIR}" RUNNING_IDENTITY=1 \
  run_case "T12 what is running"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "names the artifact the live container is running" \
  has "RUNNING_ARTIFACT=${_A_ARTIFACT}" "${LAST_OUT}"
assert "maps it back to A's identity" \
  has "RUNNING_IDENTITY=${_A_IDENTITY}" "${LAST_OUT}"
assert "moves no tag" lacks "docker tag" "${LAST_DOCKER_LOG}"
assert "brings nothing up" lacks "up -d" "${LAST_DOCKER_LOG}"
assert "takes nothing down" lacks "down -v" "${LAST_DOCKER_LOG}"
assert "probes no health endpoint" test -z "${LAST_CURL_LOG}"
rm -rf "${_T11_DIR}"

# --- T12b: RUNNING_IDENTITY with nothing up ---------------------------------
RUNNING_IDENTITY=1 SEED_IMAGES="apitest-f2-app:latest" \
  run_case "T12b what is running, with nothing up"
assert "exit 0" test "${LAST_RC}" -eq 0
# "Nothing is running" is the WORD `none`, and it is printed only after a query
# that SUCCEEDED. Changed 25 September 2026: it used to be an empty value, and
# every query that FAILED produced exactly that (T14).
assert "answers RUNNING_IDENTITY=none, which means nothing is running" \
  has_line "RUNNING_IDENTITY=none" "${LAST_OUT}"
assert "never answers with an empty value" \
  lacks_line "RUNNING_IDENTITY=" "${LAST_OUT}"
assert "changes nothing" lacks "docker tag" "${LAST_DOCKER_LOG}"

# --- T12d: something IS up but carries no identity of ours ------------------
_T12D_DIR="$(mktemp -d)"
printf 'apitest-f2-app:latest sha256:fake-SOMEBODY-ELSE\n' >"${_T12D_DIR}/images"
printf 'container:apitest-f2-app-1 sha256:fake-SOMEBODY-ELSE\n' >>"${_T12D_DIR}/images"
SCRATCH="${_T12D_DIR}" RUNNING_IDENTITY=1 \
  run_case "T12d something is up that carries no identity"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "does NOT answer empty, which would mean the target is free" \
  lacks_line "RUNNING_IDENTITY=" "${LAST_OUT}"
assert "does NOT answer none, which would mean the same" \
  lacks_line "RUNNING_IDENTITY=none" "${LAST_OUT}"
assert "answers with a token forge cannot place" \
  has "RUNNING_IDENTITY=unidentified-sha256:fake-SOMEBODY-ELSE" "${LAST_OUT}"
rm -rf "${_T12D_DIR}"

# --- T13: THE CHECK CAPTURES THE CONTAINER IT CHECKED, NOT A NAME ------------
# The third review's first fault, driven. A's candidate container stays up and
# checked while another build re-points the compose-built image NAME at B. The
# check used to resolve that name after the health check and report B as the
# checked artifact; the promote then put B live under A's identity.
_T13_DIR="$(mktemp -d)"
_T13_IDENTITY="j-cccccccccccc@3333333333333333"
_T13_PROJECT="apitest-f2-cand-j-cccccccccccc-3333333333333333"
printf 'build-b-app:latest sha256:fake-BUILD-B-T13\n' >"${_T13_DIR}/images"
printf 'apitest-f2-app:latest\n' >>"${_T13_DIR}/images"
# THE SECOND BUILD, acting in the one window it really has: while A is being
# health-checked. It gives A's compose-built image name B's image.
cat >"${_T13_DIR}/hook" <<HOOK
#!/usr/bin/env bash
export FAKE_DOCKER_LOG="${_T13_DIR}/hook-docker.log"
export FAKE_DOCKER_STATE="${_T13_DIR}/images"
exec "${FAKE_BIN}/docker" tag build-b-app:latest "${_T13_PROJECT}-app:latest"
HOOK
chmod +x "${_T13_DIR}/hook"
SCRATCH="${_T13_DIR}" CANDIDATE=1 DEPLOY_IDENTITY="${_T13_IDENTITY}" \
  FAKE_CURL_HOOK="${_T13_DIR}/hook" \
  run_case "T13 the image name is re-pointed while A's candidate is up and checked"
assert "A's check passed" test "${LAST_RC}" -eq 0
_T13_ARTIFACT="$(said CHECKED_ARTIFACT "${LAST_OUT}")"
assert "the name really was re-pointed at B during the check" \
  has "${_T13_PROJECT}-app:latest sha256:fake-BUILD-B-T13" "${LAST_STATE}"
assert "A's CHECKED_ARTIFACT is A'S CONTAINER'S image, not B's" \
  test "${_T13_ARTIFACT}" = "sha256:fake-${_T13_PROJECT}-app_latest"
assert "B's image is never reported as what was checked" \
  test "${_T13_ARTIFACT}" != "sha256:fake-BUILD-B-T13"
# And A promotes A, through the same image store.
SCRATCH="${_T13_DIR}" PROMOTE=1 DEPLOY_IDENTITY="${_T13_IDENTITY}" \
  DEPLOY_ARTIFACT="${_T13_ARTIFACT}" \
  run_case "T13b A's promote, with that name still B's"
assert "exit 0" test "${LAST_RC}" -eq 0
assert "A promotes A" \
  has "docker tag ${_T13_ARTIFACT} apitest-f2-app:latest" "${LAST_DOCKER_LOG}"
assert "B is never promoted" lacks "sha256:fake-BUILD-B-T13" "${LAST_DOCKER_LOG}"
assert "and A's identity is what is reported running" \
  has "DEPLOYED_IDENTITY=${_T13_IDENTITY}" "${LAST_OUT}"
rm -rf "${_T13_DIR}"

# --- T13c: the CONTAINER itself is replaced during the check -> refuse -------
# The other half of the same rule: if what was checked is not what is here when
# the check ends, this leg reports nothing rather than a name for it.
_T13C_DIR="$(mktemp -d)"
_T13C_IDENTITY="j-dddddddddddd@4444444444444444"
_T13C_PROJECT="apitest-f2-cand-j-dddddddddddd-4444444444444444"
printf 'build-b-app:latest sha256:fake-BUILD-B-T13C\n' >"${_T13C_DIR}/images"
cat >"${_T13C_DIR}/hook" <<HOOK
#!/usr/bin/env bash
export FAKE_DOCKER_LOG="${_T13C_DIR}/hook-docker.log"
export FAKE_DOCKER_STATE="${_T13C_DIR}/images"
"${FAKE_BIN}/docker" tag build-b-app:latest "${_T13C_PROJECT}-app:latest"
exec "${FAKE_BIN}/docker" compose -p "${_T13C_PROJECT}" -f docker-compose.yml up -d
HOOK
chmod +x "${_T13C_DIR}/hook"
SCRATCH="${_T13C_DIR}" CANDIDATE=1 DEPLOY_IDENTITY="${_T13C_IDENTITY}" \
  FAKE_CURL_HOOK="${_T13C_DIR}/hook" \
  run_case "T13c the candidate container is re-made from another image mid-check"
assert "non-zero exit" test "${LAST_RC}" -ne 0
assert "says what was checked is not what is here" \
  has "so what was checked is not what is here" "${LAST_OUT}"
assert "reports NO artifact at all" lacks "CHECKED_ARTIFACT=" "${LAST_OUT}"
rm -rf "${_T13C_DIR}"

# --- T14: A FAILED OBSERVATION IS A FAILURE, NEVER "NOTHING IS RUNNING" ------
# The third review's second fault, driven. `docker compose ps` failed, the
# script swallowed the error, exited zero and printed an empty identity — and
# forge read that as a free target and put an older result over a newer one.
_T14_DIR="$(mktemp -d)"
printf 'apitest-f2-app:latest sha256:fake-SOMETHING-LIVE\n' >"${_T14_DIR}/images"
printf 'container:apitest-f2-app-1 sha256:fake-SOMETHING-LIVE\n' >>"${_T14_DIR}/images"
SCRATCH="${_T14_DIR}" RUNNING_IDENTITY=1 FAKE_DOCKER_PS_FAILS=1 \
  run_case "T14 the query itself fails"
assert "NON-ZERO exit: a failed query is a failed run" test "${LAST_RC}" -ne 0
assert "never says an empty identity" lacks_line "RUNNING_IDENTITY=" "${LAST_OUT}"
assert "never says nothing is running" lacks_line "RUNNING_IDENTITY=none" "${LAST_OUT}"
assert "says the question could not be answered, and why" \
  has "RUNNING_IDENTITY_UNKNOWN=the query failed" "${LAST_OUT}"
assert "says plainly that this is not 'nothing is running'" \
  has "this is NOT 'nothing is running'" "${LAST_OUT}"
assert "changes nothing" lacks "docker tag" "${LAST_DOCKER_LOG}"
rm -rf "${_T14_DIR}"

# --- T14b: the container is up and cannot be asked what it runs -------------
_T14B_DIR="$(mktemp -d)"
printf 'container:apitest-f2-app-1 sha256:fake-SOMETHING-LIVE\n' >"${_T14B_DIR}/images"
SCRATCH="${_T14B_DIR}" RUNNING_IDENTITY=1 FAKE_DOCKER_INSPECT_FAILS=1 \
  run_case "T14b something is up and cannot be asked what it is running"
assert "non-zero exit" test "${LAST_RC}" -ne 0
assert "never says nothing is running" lacks_line "RUNNING_IDENTITY=none" "${LAST_OUT}"
assert "says which container could not be asked" \
  has "RUNNING_IDENTITY_UNKNOWN=" "${LAST_OUT}"
rm -rf "${_T14B_DIR}"

# --- T14c: A WARNING IS NOT AN ANSWER AND IS NOT A FAILURE -------------------
# The fourth review's smaller fault, driven. The query used to be captured with
# `2>&1`, so an ordinary engine warning — and the real engine warns readily —
# was read as the first line of the answer, failed the container-id shape check
# and made the leg exit non-zero. It failed in the safe direction, but it would
# have stopped every deploy and every candidate check on the real engine.
_T14C_DIR="$(mktemp -d)"
_T14C_IDENTITY="j-eeeeeeeeeeee@5555555555555555"
printf 'apitest-app:j-eeeeeeeeeeee-5555555555555555 sha256:fake-LIVE-E\n' >"${_T14C_DIR}/images"
printf 'apitest-f2-app:latest sha256:fake-LIVE-E\n' >>"${_T14C_DIR}/images"
printf 'container:apitest-f2-app-1 sha256:fake-LIVE-E\n' >>"${_T14C_DIR}/images"
SCRATCH="${_T14C_DIR}" RUNNING_IDENTITY=1 FAKE_DOCKER_PS_WARNS=1 \
  run_case "T14c the query succeeds and the engine warns"
assert "exit 0: a warning is not a failed observation" test "${LAST_RC}" -eq 0
assert "answers what is really running" \
  has "RUNNING_IDENTITY=${_T14C_IDENTITY}" "${LAST_OUT}"
assert "does not say the question could not be answered" \
  lacks "RUNNING_IDENTITY_UNKNOWN=" "${LAST_OUT}"
assert "the warning is never read as the answer" \
  lacks "RUNNING_IDENTITY=WARN" "${LAST_OUT}"
rm -rf "${_T14C_DIR}"

# --- T14d: and the candidate check survives the same warning ----------------
_T14D_DIR="$(mktemp -d)"
_T14D_IDENTITY="j-ffffffffffff@6666666666666666"
_T14D_PROJECT="apitest-f2-cand-j-ffffffffffff-6666666666666666"
: >"${_T14D_DIR}/images"
SCRATCH="${_T14D_DIR}" CANDIDATE=1 DEPLOY_IDENTITY="${_T14D_IDENTITY}" \
  FAKE_DOCKER_PS_WARNS=1 \
  run_case "T14d the candidate check with an engine that warns"
assert "the check passed" test "${LAST_RC}" -eq 0
assert "it captured its own container's image" \
  has "CHECKED_ARTIFACT=sha256:fake-${_T14D_PROJECT}-app_latest" "${LAST_OUT}"
assert "it never mistook the warning for a container id" \
  lacks "could not be asked which container it started" "${LAST_OUT}"
rm -rf "${_T14D_DIR}"

# --- T12c: RUNNING_IDENTITY is a mode like the others (ambiguity refused) ----
RUNNING_IDENTITY=1 PROMOTE=1 SEED_IMAGES="apitest-f2-app:latest" \
  run_case "T12c ambiguous PROMOTE+RUNNING_IDENTITY"
assert "non-zero exit" test "${LAST_RC}" -ne 0
assert "loud FATAL on ambiguous mode signal" \
  has "FATAL: ambiguous mode signal" "${LAST_OUT}"
assert "ran no docker at all" lacks "docker" "${LAST_DOCKER_LOG}"

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
