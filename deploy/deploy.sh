#!/usr/bin/env bash
#
# api_test vetted deploy script (the wrapper forge's deploy_compose step runs).
#
# CONTRACT (forge.executor.shell_steps.deploy_compose / _run_script_step):
#   * The script is invoked as a bare subprocess with NO argv:
#       subprocess.run([program], cwd=<step.params["cwd"]>, env=<os.environ (+ ENV_FILE)>)
#     so ALL inputs arrive via the ENVIRONMENT, never via command-line args.
#   * `cwd` is the profile's `cwd` (deploy/profile.yaml -> cwd:). We ALSO self-
#     anchor to the repo root via BASH_SOURCE so the compose file is found even
#     if the caller's cwd differs.
#   * `env_file` (profile compose.env_file) is exposed as $ENV_FILE (a PATH; the
#     runner never reads it — we source it here if present). This profile sets no
#     env_file, so $ENV_FILE is normally unset.
#
# MODE SIGNAL (see the C4 blocker note below). Exactly ONE mode env may be
# truthy; two or more is refused LOUDLY (deny-by-default, no guessing):
#   * Normal deploy  : all mode envs unset/false -> snapshot current image as the
#                      rollback tag, then `up -d --build`, then wait for health.
#   * O-32 revert     : $REVERT truthy       -> re-tag $ROLLBACK_IMAGE_REF as the
#                      compose image tag, then `up -d --no-build` (the ROLLBACK
#                      image serves), then wait for health.
#   * Candidate       : $CANDIDATE truthy    -> bring a THROWAWAY sandbox copy up
#                      on a candidate compose project OF THIS CHECK'S OWN
#                      (offset host port $CANDIDATE_PORT) with the candidate
#                      overlay, `up -d --build`, wait for health on the candidate
#                      port. NO rollback snapshot; the LIVE name is never touched
#                      (design §3 candidate-then-promote). It then READS THE
#                      IMAGE OFF THE CONTAINER IT STARTED, names that image with
#                      the identity forge handed over, and prints it.
#   * Promote         : $PROMOTE truthy       -> snapshot the current LIVE image as
#                      the rollback tag, re-tag THE RECORDED ARTIFACT ($DEPLOY_ARTIFACT,
#                      an image id, never a shared tag) as the live image (NO
#                      rebuild), then live `up -d --no-build`, wait for health on the
#                      live port, and INSPECT THE RUNNING CONTAINER to say what is
#                      actually running.
#   * What is running : $RUNNING_IDENTITY truthy -> read-only. Inspects the live
#                      container and prints what it is running. Changes NOTHING.
#                      A query that FAILED is never reported as "nothing is
#                      running": it prints RUNNING_IDENTITY_UNKNOWN=<reason> and
#                      exits non-zero. "Nothing is running" is the word `none`,
#                      and it is printed only after a query that SUCCEEDED.
#   * Candidate down  : $CANDIDATE_DOWN truthy -> `down -v --remove-orphans` on
#                      this check's own candidate project (teardown of the
#                      sandbox + its db volume).
#
#   The forge revert runbook (runbook_builder.build_revert_runbook) puts
#   `revert: True` and `rollback_image_ref` in the deploy_compose STEP PARAMS;
#   shell_steps.deploy_compose threads them to this script as REVERT=1 and
#   ROLLBACK_IMAGE_REF=<tag> (forge commit deff3c4f, 2026-07-16 — the O-32
#   revert-signal fix this lane surfaced). The revert logic below is proven by
#   deploy/tests/run_deploy_tests.sh against a PATH-shimmed fake docker.
#
# SAFETY: this script is EXECUTED ONLY BY FORGE AT C4 (attended). It is proven
# in this lane with a PATH-shimmed fake docker/curl harness, never run against
# the live apitest-f2 project here.
set -euo pipefail

# --- anchor to the repo root (where docker-compose.yml lives) ----------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# --- config (env-overridable; defaults are the live apitest-f2 layout) -------
COMPOSE_PROJECT="${COMPOSE_PROJECT:-apitest-f2}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
# The image the `app` service resolves to. The compose `app` service has
# `build: .` and no explicit `image:`, so compose names the built image
# <project>-<service> = apitest-f2-app:latest (verified against the live stack).
APP_IMAGE="${APP_IMAGE:-apitest-f2-app:latest}"
# The kept rollback tag this script maintains; MUST match profile.rollback_image_ref.
ROLLBACK_IMAGE_REF="${ROLLBACK_IMAGE_REF:-apitest-app:rollback-pre-deploy}"
# --- candidate-then-promote sandbox config (design §3) -----------------------
# Offset host port the candidate publishes (verified free; convention = 8902).
CANDIDATE_PORT="${CANDIDATE_PORT:-8902}"
# THE CANDIDATE PROJECT IS THIS CHECK'S OWN (25 September 2026, the third
# review). It used to be one shared name, ${COMPOSE_PROJECT}-cand, so two
# builds checking at the same time shared one compose project, one container
# and one built image name — and the second one to start replaced what the
# first one was in the middle of checking. Every candidate project this script
# makes now begins with the prefix below and ends with a token belonging to
# this check alone, so nothing another build does can land inside it.
CANDIDATE_PROJECT_PREFIX="${CANDIDATE_PROJECT_PREFIX:-${COMPOSE_PROJECT}-cand}"
# The candidate overlay layered on top of $COMPOSE_FILE (remaps the app port).
CANDIDATE_COMPOSE_FILE="${CANDIDATE_COMPOSE_FILE:-deploy/docker-compose.candidate.yml}"
# There is deliberately NO shared candidate image name here any more. The
# compose-built image name (<project>-<service>) is a name a second build can
# be given, and reading it is what the promote was doing wrong; the artifact is
# read off the CONTAINER this check started instead, by its own image id.
# Health wait (curl the app /health until it reports the DB connected).
HEALTH_URL="${HEALTH_URL:-http://localhost:8901/health}"
HEALTH_EXPECT="${HEALTH_EXPECT:-\"database\":\"connected\"}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-120}"
HEALTH_INTERVAL_SECONDS="${HEALTH_INTERVAL_SECONDS:-3}"

# Optional env file (forge exposes its PATH via $ENV_FILE); source if present.
if [[ -n "${ENV_FILE:-}" && -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "${ENV_FILE}"
  set +a
fi

log() { printf '[deploy.sh] %s\n' "$*"; }

# Echo the image id for a ref, or empty string if the ref is absent. The ref may
# itself be an image ID: docker resolves those too, which is the whole point --
# an ID is the one name in this system that cannot be moved onto another image.
image_id() {
  docker image inspect --format '{{.Id}}' "$1" 2>/dev/null || true
}

# The image reference that names ONE artifact and can never be given to another:
# the prefix this project uses, plus the identity forge handed over with its one
# '@' turned into a dash (an image reference may not carry '@' in a tag).
identity_ref() {
  printf '%s:%s\n' "${IDENTITY_IMAGE_PREFIX:-apitest-app}" "${1//@/-}"
}

# ASK A COMPOSE PROJECT WHICH CONTAINER IS SERVING ITS app SERVICE.
#
# WHAT CHANGED HERE (25 September 2026, the third review of the executor
# stage). This used to be `... ps -q app 2>/dev/null | head -n1 || true`, which
# threw the query's own verdict away: a docker that FAILED gave an empty answer
# and an exit code of zero, and the read-only mode below then told forge that
# NOTHING WAS RUNNING. Forge read that as a free target and deployed an older
# result over a newer one. That was driven with a failing docker, so it is a
# fact about this script rather than a worry about it.
#
# A failed observation is a FAILURE. The answer is one line:
#   ok <container id>   -- a query that SUCCEEDED and found that container
#   ok                  -- a query that SUCCEEDED and found nothing up
#   error <reason>      -- the query did not succeed; NOTHING may be concluded
#
# AND THE TWO STREAMS ARE KEPT APART (26 September 2026, the fourth review).
# The first cure captured the query with `2>&1`, which put the engine's own
# chatter in front of the answer: a docker that SUCCEEDS and warns -- and the
# real engine warns readily, e.g. about an obsolete compose attribute -- had
# its warning read as the first line of the answer, failed the container-id
# shape check, and made the leg exit non-zero. It failed safely, in that
# nothing was deployed, but it would have stopped every deploy and every
# candidate check. Ids come from stdout; stderr is kept for the REASON only.
compose_container() {
  local project="$1" out rc first chatter errs
  errs="$(mktemp "${TMPDIR:-/tmp}/deploy-sh-query.XXXXXX")"
  out="$(docker compose -p "${project}" -f "${COMPOSE_FILE}" ps -q app 2>"${errs}")" \
    && rc=0 || rc=$?
  chatter="$(tr '\n' ' ' <"${errs}" | cut -c1-160)"
  rm -f "${errs}"
  if ((rc != 0)); then
    printf 'error the query failed: `docker compose -p %s ps -q app` exited %s (%s)\n' \
      "${project}" "${rc}" "${chatter}"
    return 0
  fi
  first="$(printf '%s' "${out}" | head -n1)"
  # An answer that cannot be read is not an answer. `ps -q` prints container
  # ids, one per line; anything else means the query's own output could not be
  # understood, and a guess at what it meant would be the same defect again.
  if [[ -n "${first}" && ! "${first}" =~ ^[A-Za-z0-9_.-]+$ ]]; then
    printf 'error the query answered something this script cannot read as a container id: %s\n' \
      "$(printf '%s' "${first}" | cut -c1-160)"
    return 0
  fi
  printf 'ok %s\n' "${first}"
}

# The container id currently serving the LIVE compose project's app service, in
# the same three-way shape as above.
live_container() {
  compose_container "${COMPOSE_PROJECT}"
}

# The image id a RUNNING container was started from -- read off the container
# itself, never off a tag. This is the line that makes "what is running" a fact
# rather than a repetition of what this script was told: a tag can be moved onto
# another image after the container started; the container's own image id cannot.
#
# Non-zero when the container could not be asked (25 September 2026): a docker
# that fails here is a failed observation too, and the caller says so rather
# than carrying an empty string forward as if it meant something.
running_image_id() {
  local cid="$1" out
  if [[ -z "${cid}" ]]; then
    return 1
  fi
  out="$(docker inspect --format '{{.Image}}' "${cid}" 2>/dev/null)" || return 1
  out="$(printf '%s' "${out}" | head -n1)"
  [[ -z "${out}" ]] && return 1
  printf '%s\n' "${out}"
}

# The identity name carried by an image id, worked out from the identity-prefixed
# tags that image has. Empty when the image carries none -- which forge reads as
# "this target cannot be accounted for", and it then deploys nothing.
#
# The identity text is "<name>@<fingerprint>" and the tag is "<name>-<fingerprint>",
# where the fingerprint carries no dash, so the LAST dash is the one that was the
# '@'. Nothing else in this file needs to know the shape of an identity.
#
# Non-zero when the IMAGE ITSELF could not be inspected (25 September 2026):
# that is a failed observation, not an image without an identity, and the two
# are answered differently.
identity_of_image() {
  local id="$1" tags tag body
  [[ -z "${id}" ]] && return 1
  tags="$(docker image inspect --format '{{range .RepoTags}}{{println .}}{{end}}' \
    "${id}" 2>/dev/null)" || return 1
  while IFS= read -r tag; do
    [[ -z "${tag}" ]] && continue
    case "${tag}" in
      "${IDENTITY_IMAGE_PREFIX:-apitest-app}":*) ;;
      *) continue ;;
    esac
    body="${tag#*:}"
    case "${body}" in
      rollback-* | latest) continue ;;
    esac
    [[ "${body}" != *-* ]] && continue
    printf '%s@%s\n' "${body%-*}" "${body##*-}"
    return 0
  done <<<"${tags}"
  return 0
}

# THE TOKEN THAT MAKES A CANDIDATE PROJECT THIS CHECK'S OWN. It is the
# identity forge handed over, reduced to what a compose project name may
# carry, so the teardown that is handed the same identity finds the same
# project. $CANDIDATE_TOKEN overrides it; with neither, the caller decides
# what to do (the check makes a fresh one, the teardown goes looking).
candidate_token() {
  local raw="${CANDIDATE_TOKEN:-${DEPLOY_IDENTITY:-}}"
  [[ -z "${raw}" ]] && return 1
  raw="$(printf '%s' "${raw}" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9_-' '-')"
  raw="${raw%%-}"
  [[ -z "${raw}" ]] && return 1
  printf '%s\n' "${raw}"
}

# Truthy test for the env var NAMED by $1 (indirect expansion), so one helper
# serves every mode flag: REVERT / CANDIDATE / PROMOTE / CANDIDATE_DOWN.
is_truthy() {
  case "${!1:-}" in
    1 | true | TRUE | yes | YES) return 0 ;;
    *) return 1 ;;
  esac
}

# Poll HEALTH_URL until the body contains HEALTH_EXPECT; fail loud on timeout.
wait_for_health() {
  local deadline=$((SECONDS + HEALTH_TIMEOUT_SECONDS))
  local body=""
  log "waiting for health: ${HEALTH_URL} to contain [${HEALTH_EXPECT}] (timeout ${HEALTH_TIMEOUT_SECONDS}s)"
  while ((SECONDS < deadline)); do
    if body="$(curl -fsS "${HEALTH_URL}" 2>/dev/null)" \
      && printf '%s' "${body}" | grep -qF -- "${HEALTH_EXPECT}"; then
      log "health OK: ${body}"
      return 0
    fi
    sleep "${HEALTH_INTERVAL_SECONDS}"
  done
  log "FATAL: ${HEALTH_URL} did not become healthy within ${HEALTH_TIMEOUT_SECONDS}s"
  return 1
}

deploy_normal() {
  local cur_id
  cur_id="$(image_id "${APP_IMAGE}")"
  log "MODE=normal project=${COMPOSE_PROJECT} app_image=${APP_IMAGE}"
  log "before: ${APP_IMAGE}=${cur_id:-<none>} rollback=${ROLLBACK_IMAGE_REF}=$(image_id "${ROLLBACK_IMAGE_REF}")"
  if [[ -n "${cur_id}" ]]; then
    # Snapshot the currently-running build as the rollback image BEFORE we
    # replace it, so an O-32 revert can bring the prior build back up.
    docker tag "${APP_IMAGE}" "${ROLLBACK_IMAGE_REF}"
    log "snapshotted rollback: ${ROLLBACK_IMAGE_REF}=$(image_id "${ROLLBACK_IMAGE_REF}")"
  else
    # First-ever deploy: nothing running to snapshot (|| true per the contract).
    docker tag "${APP_IMAGE}" "${ROLLBACK_IMAGE_REF}" || true
    log "no current ${APP_IMAGE} to snapshot (first deploy)"
  fi
  docker compose -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}" up -d --build
  wait_for_health
  log "after: ${APP_IMAGE}=$(image_id "${APP_IMAGE}")"
  log "deploy complete"
}

deploy_revert() {
  local rb_id
  rb_id="$(image_id "${ROLLBACK_IMAGE_REF}")"
  log "MODE=revert project=${COMPOSE_PROJECT} rollback_image_ref=${ROLLBACK_IMAGE_REF}"
  if [[ -z "${rb_id}" ]]; then
    # Loud terminal failure: no kept image to revert to (mirrors forge's own
    # missing-rollback loud fail in stage._run_revert).
    log "FATAL: rollback image ${ROLLBACK_IMAGE_REF} not found -- cannot revert; refusing to keep serving the unverified build"
    return 1
  fi
  log "before: ${APP_IMAGE}=$(image_id "${APP_IMAGE}") rollback=${ROLLBACK_IMAGE_REF}=${rb_id}"
  # Re-tag the kept rollback image as the compose image tag so `up --no-build`
  # brings the ROLLBACK image up (no rebuild -- we re-serve a known-good image).
  docker tag "${ROLLBACK_IMAGE_REF}" "${APP_IMAGE}"
  log "re-tagged ${ROLLBACK_IMAGE_REF} -> ${APP_IMAGE}=$(image_id "${APP_IMAGE}")"
  docker compose -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}" up -d --no-build
  wait_for_health
  log "after: ${APP_IMAGE}=$(image_id "${APP_IMAGE}") (serving rollback ${rb_id})"
  log "revert complete"
}

deploy_candidate() {
  # A throwaway sandbox copy on a candidate project OF THIS CHECK'S OWN, on the
  # offset host port. NO rollback snapshot is taken and the LIVE image/name is
  # NEVER touched: a failing candidate is simply torn down (candidate_down) with
  # the live leg untouched. Health is probed on the CANDIDATE port (the app
  # still listens on 8901 inside the container; only the host publish moves).
  #
  # WHAT CHANGED HERE, TWICE.
  #
  # 24 September 2026, the second review. The promote used to make the unique
  # name FROM the shared candidate image name, AT PROMOTE TIME, so a second
  # build that re-pointed that name between the check and the promote had its
  # image put live under this build's identity.
  #
  # 25 September 2026, the third review. That cure moved the read earlier but
  # still READ A SHARED NAME: this leg resolved ${CANDIDATE_PROJECT}-app:latest
  # after the health check, and a reviewer kept this candidate's container up
  # while another build re-pointed that name at ITS image. The line reported as
  # the checked artifact was the other build's, and the promote then put the
  # other build's work live under this build's identity. Reading the shared
  # name EARLIER would not have cured it either: the name is not authoritative
  # at any moment, because it is not this check's to begin with.
  #
  # So two things are true here now and neither depends on a name:
  #   1. the compose project, its container and its built image belong to THIS
  #      CHECK -- the token is the identity forge handed over, or a fresh one --
  #      so no other build's check can land inside it;
  #   2. the artifact is read OFF THE CONTAINER THIS CHECK STARTED, by that
  #      container's own image id, before the health check and again after it,
  #      and the two must be the same container and the same image. Anything
  #      else means the thing that was checked is not the thing that is here,
  #      and this leg refuses rather than reporting a name for it.
  local project token cid cid_after started_on running_now checked_ref
  if ! token="$(candidate_token)"; then
    # No identity and no token handed over: a check nobody will promote. It
    # still gets a project of its own rather than a shared one.
    token="fresh-$(date -u +%Y%m%d%H%M%S)-$$"
    log "no DEPLOY_IDENTITY and no CANDIDATE_TOKEN were handed to this check, so it made a token of its own: ${token}"
  fi
  project="${CANDIDATE_PROJECT_PREFIX}-${token}"
  HEALTH_URL="http://localhost:${CANDIDATE_PORT}/health"
  log "MODE=candidate project=${project} port=${CANDIDATE_PORT}"
  log "candidate is a throwaway sandbox of this check's own: no rollback snapshot, the LIVE name is untouched, and no other build shares this compose project"
  docker compose -p "${project}" \
    -f "${COMPOSE_FILE}" -f "${CANDIDATE_COMPOSE_FILE}" up -d --build
  # WHICH CONTAINER THIS CHECK STARTED, and what it is running -- before the
  # health check, so what is checked and what is captured are the same thing.
  cid="$(compose_container "${project}")"
  if [[ "${cid}" == error\ * ]]; then
    log "FATAL: ${project} could not be asked which container it started -- ${cid#error }. Nothing may be concluded from a failed query, so this check reports no artifact (LIVE untouched)"
    return 1
  fi
  cid="${cid#ok}"
  cid="${cid# }"
  if [[ -z "${cid}" ]]; then
    log "FATAL: nothing came up on ${project}, so there is no container whose image could be captured. Refusing (LIVE untouched)"
    return 1
  fi
  if ! started_on="$(running_image_id "${cid}")"; then
    log "FATAL: container ${cid} is up on ${project} and could not be asked which image it is running. Refusing (LIVE untouched)"
    return 1
  fi
  log "the candidate this check started: container=${cid} image=${started_on}"
  wait_for_health
  # AND AGAIN, AFTER THE CHECK. The thing that passed the health check has to
  # be the thing whose id is reported, or the report is about something else.
  cid_after="$(compose_container "${project}")"
  if [[ "${cid_after}" == error\ * ]]; then
    log "FATAL: ${project} passed its health check and then could not be asked what it is running -- ${cid_after#error }. Refusing (LIVE untouched)"
    return 1
  fi
  cid_after="${cid_after#ok}"
  cid_after="${cid_after# }"
  if [[ "${cid_after}" != "${cid}" ]]; then
    log "FATAL: the container on ${project} changed during the check (${cid} -> ${cid_after:-<none>}), so what was checked is not what is here. Refusing (LIVE untouched)"
    return 1
  fi
  if ! running_now="$(running_image_id "${cid}")"; then
    log "FATAL: container ${cid} could not be asked which image it is running after the check. Refusing (LIVE untouched)"
    return 1
  fi
  if [[ "${running_now}" != "${started_on}" ]]; then
    log "FATAL: container ${cid} was started from ${started_on} and is now running ${running_now}, so what was checked is not what is here. Refusing (LIVE untouched)"
    return 1
  fi
  if [[ -n "${DEPLOY_IDENTITY:-}" ]]; then
    # PIN IT NOW, under a name nothing else can be given.
    checked_ref="$(identity_ref "${DEPLOY_IDENTITY}")"
    docker tag "${started_on}" "${checked_ref}"
    log "named what is being checked: ${checked_ref}=$(image_id "${checked_ref}")"
  else
    log "no DEPLOY_IDENTITY was handed to this check, so the artifact is reported by its own id alone"
  fi
  # THE LINE FORGE READS BACK AND RECORDS. It is the artifact's own immutable
  # identity, read off the container that was checked, and it is what the
  # promote will be handed.
  printf 'CHECKED_ARTIFACT=%s\n' "${started_on}"
  log "candidate up + healthy on :${CANDIDATE_PORT} (project ${project}, container ${cid}, image ${started_on})"
}

running_identity() {
  # READ-ONLY. Forge asks this before it decides whether to deploy anything, so
  # that a decision is made against what the target is ACTUALLY running rather
  # than against a line in forge's own ledger that a crash may have left stale.
  # It changes nothing: no tag is moved, no compose project is brought up or
  # down, and it is safe to run at any time.
  #
  # THE ANSWER IS ONE LINE, and it says one of exactly three things:
  #   RUNNING_IDENTITY=<token>          -- that is what is running here
  #   RUNNING_IDENTITY=none             -- NOTHING is running here, and this is
  #                                        said only after a query that SUCCEEDED
  #   RUNNING_IDENTITY_UNKNOWN=<reason> -- the question could not be answered
  #                                        (exit is non-zero as well)
  #
  # WHAT CHANGED HERE (25 September 2026, the third review of the executor
  # stage). "Nothing is running" used to be an EMPTY value, and every query
  # that FAILED produced exactly that: the docker call's error was thrown away,
  # the empty answer was printed, forge read a free target, and an older result
  # went over a newer one. It was driven with a failing docker. An empty
  # answer is not printed any more in any circumstance, and the only way this
  # project says the target is free is the word `none` after a query that
  # worked. "Something is up but I cannot name it" is still a token forge
  # cannot place, which stops the deploy just as firmly.
  local answer cid running identity
  answer="$(live_container)"
  if [[ "${answer}" == error\ * ]]; then
    log "MODE=running-identity project=${COMPOSE_PROJECT}: THE QUESTION COULD NOT BE ANSWERED -- ${answer#error }"
    log "this is NOT 'nothing is running': nothing at all may be concluded from a query that failed"
    printf 'RUNNING_IDENTITY_UNKNOWN=%s\n' "${answer#error }"
    return 1
  fi
  cid="${answer#ok}"
  cid="${cid# }"
  if [[ -z "${cid}" ]]; then
    log "MODE=running-identity project=${COMPOSE_PROJECT}: the query succeeded and nothing is up"
    printf 'RUNNING_IDENTITY=none\n'
    return 0
  fi
  if ! running="$(running_image_id "${cid}")"; then
    log "MODE=running-identity project=${COMPOSE_PROJECT}: container ${cid} is up and could not be asked which image it is running"
    printf 'RUNNING_IDENTITY_UNKNOWN=container %s is up on %s and could not be asked which image it is running\n' \
      "${cid}" "${COMPOSE_PROJECT}"
    return 1
  fi
  log "MODE=running-identity project=${COMPOSE_PROJECT} container=${cid} image=${running}"
  printf 'RUNNING_ARTIFACT=%s\n' "${running}"
  if ! identity="$(identity_of_image "${running}")"; then
    log "the image ${running} could not be inspected, so this project cannot say what it is"
    printf 'RUNNING_IDENTITY_UNKNOWN=the image %s the live container is running could not be inspected\n' \
      "${running}"
    return 1
  fi
  if [[ -z "${identity}" ]]; then
    # Something IS running and this project cannot say which build it is: the
    # image carries no identity tag. Saying the target is free here would be
    # the opposite of the truth.
    log "the running image carries no identity of this project's own"
    printf 'RUNNING_IDENTITY=unidentified-%s\n' "${running}"
    return 0
  fi
  printf 'RUNNING_IDENTITY=%s\n' "${identity}"
}

deploy_promote() {
  # Promote to LIVE the exact artifact forge checked -- named by its own
  # immutable id, captured at the check -- and then say what is running by
  # INSPECTING THE RUNNING CONTAINER.
  #
  # WHY THIS CHANGED, TWICE.
  #
  # 23 September 2026 (forge's one-true-copy design pass, item 1, second
  # revision section C). This used to re-tag one shared candidate name --
  # ${CANDIDATE_APP_IMAGE} -- as the live tag. That name is SHARED: a second
  # build's candidate leg overwrites it.
  #
  # 24 September 2026, after the stage's second review. The first cure was not
  # a cure. It still READ THE SHARED NAME, at promote time, and only then gave
  # what it found the identity's tag. So a second build that replaced the
  # shared name between the check and this promote had ITS image given THIS
  # build's identity, put live, and reported back as this build's identity --
  # which was driven with a fake docker and is the exact failure the design
  # exists to prevent. Making a unique name out of a shared one, late, is not
  # capturing an identity.
  #
  # The artifact is captured WHERE IT IS CHECKED (deploy_candidate above), by
  # its own image id. Forge records that id and hands it back here as
  # $DEPLOY_ARTIFACT. This leg:
  #
  #   1. resolves $DEPLOY_ARTIFACT and refuses unless it is still exactly that
  #      artifact. The shared candidate name is NEVER read here;
  #   2. promotes THAT artifact by its id;
  #   3. asks the LIVE CONTAINER which image it is running, and reports the
  #      identity only when that container's own image id is the recorded
  #      artifact.
  #
  # Forge compares the reported line, as text, with the identity it handed
  # over; anything but an exact match is a FAILED deploy. Forge knows nothing
  # about images: what an identity IS belongs here, to the project.
  local artifact cur_id promoted_ref cid live_running running
  if [[ -z "${DEPLOY_IDENTITY:-}" ]]; then
    log "FATAL: no DEPLOY_IDENTITY was handed to this promote. This script promotes the exact thing that was checked, by an identity that cannot be reused; promoting the shared candidate name instead is the defect this refuses. (LIVE untouched)"
    return 1
  fi
  if [[ -z "${DEPLOY_ARTIFACT:-}" ]]; then
    log "FATAL: no DEPLOY_ARTIFACT was handed to this promote. The artifact is captured when the candidate is CHECKED and recorded by forge; without it this leg would have to resolve the shared candidate name, which is exactly the defect it refuses. (LIVE untouched)"
    return 1
  fi
  log "MODE=promote project=${COMPOSE_PROJECT} identity=${DEPLOY_IDENTITY} artifact=${DEPLOY_ARTIFACT} -> live_image=${APP_IMAGE}"
  # 0) RESOLVE THE RECORDED ARTIFACT, BY ITS OWN ID. An id resolves to itself
  #    or to nothing; it cannot resolve to somebody else's build.
  artifact="$(image_id "${DEPLOY_ARTIFACT}")"
  if [[ -z "${artifact}" ]]; then
    log "FATAL: the artifact that was checked (${DEPLOY_ARTIFACT}) is not here any more -- it cannot be promoted, and the shared candidate name is not a substitute for it. (LIVE untouched)"
    return 1
  fi
  if [[ "${artifact}" != "${DEPLOY_ARTIFACT}" ]]; then
    log "FATAL: ${DEPLOY_ARTIFACT} now resolves to ${artifact}, which is a different image -- refusing to promote something other than what was checked. (LIVE untouched)"
    return 1
  fi
  # 1) Re-assert the identity's own name on that artifact, so a person reading
  #    the running thing's labels can see where it came from. It is a name for
  #    the SAME image; nothing is resolved through it.
  promoted_ref="$(identity_ref "${DEPLOY_IDENTITY}")"
  docker tag "${artifact}" "${promoted_ref}"
  log "the checked artifact ${artifact} is named ${promoted_ref}"
  cur_id="$(image_id "${APP_IMAGE}")"
  # 2) Snapshot the current LIVE build as the rollback tag BEFORE we overwrite it.
  if [[ -n "${cur_id}" ]]; then
    docker tag "${APP_IMAGE}" "${ROLLBACK_IMAGE_REF}"
    log "snapshotted rollback: ${ROLLBACK_IMAGE_REF}=$(image_id "${ROLLBACK_IMAGE_REF}")"
  else
    docker tag "${APP_IMAGE}" "${ROLLBACK_IMAGE_REF}" || true
    log "no current ${APP_IMAGE} to snapshot (first promote)"
  fi
  # 3) Give the live tag to THE RECORDED ARTIFACT, by id -- NO rebuild.
  docker tag "${artifact}" "${APP_IMAGE}"
  log "promoted artifact: ${artifact} -> ${APP_IMAGE}=$(image_id "${APP_IMAGE}")"
  # 4) Bring the LIVE project up on the promoted image WITHOUT rebuilding.
  docker compose -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}" up -d --no-build
  wait_for_health
  # 5) SAY WHAT IS RUNNING, read off the RUNNING CONTAINER. A tag says what a
  #    name points at now; the container says what it was started from, which
  #    is the only thing that answers "what is running".
  #    A query that FAILED is not an answer (25 September 2026): saying "not
  #    this identity" on the strength of a docker that fell over would put a
  #    red ending on a deploy that may well have worked, and saying the
  #    identity would claim something nobody looked at. It exits loudly instead
  #    and reports no identity at all, which forge reads as a failed deploy
  #    with the target's state unknown -- which is exactly what it is.
  cid="$(live_container)"
  if [[ "${cid}" == error\ * ]]; then
    log "FATAL: the promote ran and ${COMPOSE_PROJECT} could not then be asked what it is running -- ${cid#error }. What is live is NOT known, and this leg will not guess either way."
    return 1
  fi
  cid="${cid#ok}"
  cid="${cid# }"
  if [[ -z "${cid}" ]]; then
    log "FATAL: the promote ran and nothing is up on ${COMPOSE_PROJECT}. What is live is NOT what was checked."
    return 1
  fi
  if ! live_running="$(running_image_id "${cid}")"; then
    log "FATAL: the promote ran and container ${cid} could not be asked which image it is running. What is live is NOT known."
    return 1
  fi
  if [[ "${live_running}" == "${artifact}" ]]; then
    running="${DEPLOY_IDENTITY}"
  else
    running="not-${DEPLOY_IDENTITY}"
    log "WARNING: the live container ${cid} is running ${live_running}, not the artifact that was checked (${artifact})"
  fi
  log "after: container=${cid} image=${live_running} (checked artifact ${artifact})"
  # THE TWO LINES FORGE READS BACK. The first is the identity comparison the
  # press fails a deploy on; the second is the artifact, for the record.
  printf 'DEPLOYED_ARTIFACT=%s\n' "${live_running}"
  printf 'DEPLOYED_IDENTITY=%s\n' "${running}"
  log "promote complete"
}

tear_one_candidate_down() {
  local project="$1"
  log "tearing ${project} down with its volumes"
  docker compose -p "${project}" \
    -f "${COMPOSE_FILE}" -f "${CANDIDATE_COMPOSE_FILE}" down -v --remove-orphans
  log "candidate ${project} torn down"
}

candidate_down() {
  # Teardown helper: remove a candidate project + its db volume + orphans. Used
  # when a candidate gate FAILS (live never touched) or after a promote when
  # candidate.keep is false. The LIVE project is never named here.
  #
  # Changed 25 September 2026 with the candidate project itself. A teardown
  # that is handed the same identity the check was handed tears down exactly
  # that check's project and nothing else. One that is handed nothing goes and
  # LOOKS for candidate projects of this repository's, because there is no
  # longer one name it could assume -- and it says which ones it found.
  local project token found any
  if token="$(candidate_token)"; then
    project="${CANDIDATE_PROJECT_PREFIX}-${token}"
    log "MODE=candidate_down project=${project} (named by the identity this teardown was handed)"
    tear_one_candidate_down "${project}"
    return 0
  fi
  log "MODE=candidate_down: no identity and no token were handed to this teardown, so it asks docker which candidate projects of ${CANDIDATE_PROJECT_PREFIX} are up"
  found="$(docker compose ls --all -q 2>/dev/null || true)"
  any=0
  while IFS= read -r project; do
    [[ -z "${project}" ]] && continue
    case "${project}" in
      "${CANDIDATE_PROJECT_PREFIX}"-*) ;;
      *) continue ;;
    esac
    any=1
    tear_one_candidate_down "${project}"
  done <<<"${found}"
  if ((any == 0)); then
    log "no candidate project of ${CANDIDATE_PROJECT_PREFIX} is up; nothing to tear down"
  fi
}

# Resolve the single active mode from the truthy flags; refuse ambiguity loudly.
resolve_and_run() {
  local modes=()
  if is_truthy REVERT; then modes+=("revert"); fi
  if is_truthy CANDIDATE; then modes+=("candidate"); fi
  if is_truthy PROMOTE; then modes+=("promote"); fi
  if is_truthy CANDIDATE_DOWN; then modes+=("candidate_down"); fi
  if is_truthy RUNNING_IDENTITY; then modes+=("running_identity"); fi
  if ((${#modes[@]} > 1)); then
    log "FATAL: ambiguous mode signal (${modes[*]}); set EXACTLY ONE of REVERT / CANDIDATE / PROMOTE / CANDIDATE_DOWN / RUNNING_IDENTITY (or none for a normal deploy). Refusing."
    return 2
  fi
  case "${modes[0]:-normal}" in
    revert) deploy_revert ;;
    candidate) deploy_candidate ;;
    promote) deploy_promote ;;
    candidate_down) candidate_down ;;
    running_identity) running_identity ;;
    normal) deploy_normal ;;
  esac
}

main() {
  log "repo_root=${REPO_ROOT}"
  resolve_and_run
}

main "$@"
